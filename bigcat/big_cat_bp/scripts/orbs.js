// Capture orbs: catch a mob into an item and release it again later. Hand-written (not generated).
//
// Two kinds share this code (see ORBS):
//   * Cat Orb       (mymod:cat_orb)      catches Big Cats only.
//   * Creature Orb  (mymod:creature_orb) catches any mob except players, bosses and objects.
//
// Capture: use an empty orb on a mob (right-click it, or aim at it within CAPTURE_RANGE blocks
//   and use). The mob is saved, with everything about it (owner, name, age, health, coat,
//   collar, villager trades...), into a world structure, and removed. The orb in your hand
//   becomes the matching "full" orb that remembers which structure holds the mob.
// Release: use the full orb on a block (or aim at one within RELEASE_RANGE). The structure is
//   placed there, entities only, so the same mob comes back, and is then deleted. You get the
//   empty orb back.
//
// The mob is saved where it stands (a 1-block structure around its feet). If anything else is in
// that block, the capture is refused, so nothing else ever gets copied into the orb.
// Players are handled by trap_orb.js instead: the game cannot save a player into a structure.

import { world, system, ItemStack, StructureSaveMode } from "@minecraft/server";

const CAT_ID = "mymod:big_cat";
const COAT_PROPERTY = "mymod:coat";

const PROP_STRUCTURE = "bigcat_orb_structure"; // on a full orb: structure id
const PROP_CAT_NAME = "bigcat_orb_name"; // on a full orb: name shown in messages

const CAPTURE_RANGE = 8; // blocks, when aiming instead of clicking the mob
const RELEASE_RANGE = 8;
const COOLDOWN_TICKS = 6; // one click can fire both a before-event and itemUse

// Too powerful to put in a pocket.
const BOSSES = new Set(["minecraft:ender_dragon", "minecraft:wither", "minecraft:warden", "minecraft:elder_guardian"]);

/** Readable name: the name tag if it has one, else the id ("minecraft:villager_v2" -> "Villager"). */
function mobLabel(entity) {
  if (entity.nameTag) return entity.nameTag;
  if (entity.typeId === CAT_ID) {
    const coat = entity.getProperty(COAT_PROPERTY);
    return typeof coat === "number" ? `Big Cat (coat ${String(coat).padStart(3, "0")})` : "Big Cat";
  }
  const bare = entity.typeId.split(":").pop().replace(/_v\d+$/, "");
  return bare
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function ownedBySomeoneElse(entity, player) {
  const t = entity.getComponent("minecraft:tameable");
  return !!(t?.isTamed && t.tamedToPlayerId && t.tamedToPlayerId !== player.id);
}

/** Orb kinds. `refuse` returns a message when the orb can't take this entity, else undefined. */
const ORBS = [
  {
    name: "Cat Orb",
    empty: "mymod:cat_orb",
    full: "mymod:cat_orb_full",
    aimHint: "§7Aim at a Big Cat to catch it.",
    refuse(entity, player) {
      if (entity.typeId !== CAT_ID) return "§7The Cat Orb only holds Big Cats.";
      if (ownedBySomeoneElse(entity, player)) return "§cThat cat belongs to someone else.";
    },
    releaseSound: "mob.cat.meow",
  },
  {
    name: "Creature Orb",
    empty: "mymod:creature_orb",
    full: "mymod:creature_orb_full",
    aimHint: "§7Aim at a creature to catch it.",
    refuse(entity, player) {
      if (entity.typeId === "minecraft:player") return "§7Players need a Player Trap Orb.";
      if (BOSSES.has(entity.typeId)) return "§cThat's far too powerful to catch!";
      if (!entity.getComponent("minecraft:health") || entity.matches({ families: ["inanimate"] })) {
        return "§7That's not a creature.";
      }
      if (ownedBySomeoneElse(entity, player)) return "§cThat pet belongs to someone else.";
    },
    releaseSound: undefined,
  },
];
const BY_EMPTY = new Map(ORBS.map((o) => [o.empty, o]));
const BY_FULL = new Map(ORBS.map((o) => [o.full, o]));

/** playerId -> tick of the last orb action */
const lastAction = new Map();

function onCooldown(player) {
  const now = system.currentTick;
  if (now - (lastAction.get(player.id) ?? -1000) < COOLDOWN_TICKS) return true;
  lastAction.set(player.id, now);
  return false;
}

function tell(player, text) {
  player.onScreenDisplay.setActionBar(text);
}

/** The held stack, re-read when we act (the event's copy can be stale). */
function heldSlot(player, expectedId) {
  const container = player.getComponent("minecraft:inventory")?.container;
  if (!container) return undefined;
  const slot = player.selectedSlotIndex;
  const item = container.getItem(slot);
  if (item?.typeId !== expectedId) return undefined;
  return { container, slot, item };
}

/** Put `stack` (the filled orb) in the player's hand. Any other empty orbs from the held stack
 *  move to the rest of the inventory, or drop at their feet if it's full. */
function giveBack(player, held, stack) {
  const rest = held.item.amount - 1;
  held.container.setItem(held.slot, stack);
  if (rest <= 0) return;
  const empties = held.item.clone();
  empties.amount = rest;
  const leftover = held.container.addItem(empties);
  if (leftover) player.dimension.spawnItem(leftover, player.location);
}

function fullOrb(orb, entity, structureId) {
  const label = mobLabel(entity);
  const s = new ItemStack(orb.full, 1);
  s.setDynamicProperty(PROP_STRUCTURE, structureId);
  s.setDynamicProperty(PROP_CAT_NAME, label);
  s.nameTag = `${orb.name}: ${label}`;
  const lore = [`§7Holds §f${label}`];
  if (entity.typeId === CAT_ID) {
    const coat = entity.getProperty(COAT_PROPERTY);
    if (typeof coat === "number") lore.push(`§7Coat §f${String(coat).padStart(3, "0")}`);
  }
  const tameable = entity.getComponent("minecraft:tameable");
  if (tameable) lore.push(tameable.isTamed ? "§aTamed" : "§eWild");
  s.setLore(lore);
  return s;
}

function capture(player, orb, entity) {
  if (!entity?.isValid) return;
  const held = heldSlot(player, orb.empty);
  if (!held) return;
  const refusal = orb.refuse(entity, player);
  if (refusal) {
    tell(player, refusal);
    return;
  }

  const dim = entity.dimension;
  const from = entity.location;
  const label = mobLabel(entity);

  // Save the 1-block area the mob stands in. Anything else standing in that block (another
  // mob, a dropped item, an XP orb) would be copied into the orb too, so refuse instead.
  // (The mob is never moved: wild mobs moved far from every player despawn instantly.)
  const spot = { x: Math.floor(from.x), y: Math.floor(from.y), z: Math.floor(from.z) };
  const others = dim
    .getEntities({ location: spot, volume: { x: 0.999, y: 0.999, z: 0.999 } })
    .filter((e) => e.id !== entity.id);
  if (others.length) {
    tell(player, `§7Too crowded: something else is right next to ${label}. Try again when it moves.`);
    return;
  }

  const structureId = `mymod:orb_${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`;
  try {
    world.structureManager.createFromWorld(structureId, dim, spot, spot, {
      includeBlocks: false,
      includeEntities: true,
      saveMode: StructureSaveMode.World,
    });
  } catch (e) {
    console.warn(`[bigcat orb] capture failed: ${e}`);
    tell(player, `§cThe orb fizzled. ${label} is still there.`);
    return;
  }
  // The mob is deleted only after the save succeeded.
  const stack = fullOrb(orb, entity, structureId);
  entity.remove();
  giveBack(player, held, stack);
  dim.spawnParticle("minecraft:basic_portal_particle", { x: from.x, y: from.y + 1, z: from.z });
  dim.spawnParticle("minecraft:villager_happy", { x: from.x, y: from.y + 1.5, z: from.z });
  player.playSound("mob.shulker.close", { pitch: 1.4 });
  tell(player, `§dCaught ${label}!`);
}

function release(player, orb, location) {
  const held = heldSlot(player, orb.full);
  if (!held) return;
  const structureId = held.item.getDynamicProperty(PROP_STRUCTURE);
  const label = held.item.getDynamicProperty(PROP_CAT_NAME) ?? "your creature";

  const structure = typeof structureId === "string" ? world.structureManager.get(structureId) : undefined;
  if (!structure) {
    tell(player, "§cThis orb is empty. Its creature could not be found.");
    held.container.setItem(held.slot, new ItemStack(orb.empty, 1));
    return;
  }
  try {
    world.structureManager.place(structure, player.dimension, location, {
      includeBlocks: false,
      includeEntities: true,
    });
  } catch (e) {
    console.warn(`[bigcat orb] release failed: ${e}`);
    tell(player, `§c${label} can't come out here. Try somewhere else.`);
    return;
  }
  try {
    world.structureManager.delete(structureId);
  } catch (e) {
    console.warn(`[bigcat orb] could not delete structure ${structureId}: ${e}`);
  }
  held.container.setItem(held.slot, new ItemStack(orb.empty, 1));

  const c = { x: location.x + 0.5, y: location.y + 1, z: location.z + 0.5 };
  player.dimension.spawnParticle("minecraft:basic_portal_particle", c);
  player.dimension.spawnParticle("minecraft:heart_particle", { x: c.x, y: c.y + 1.5, z: c.z });
  player.playSound("random.pop", { pitch: 0.8 });
  if (orb.releaseSound) player.playSound(orb.releaseSound);
  tell(player, `§dWelcome back, ${label}!`);
}

/** Where a released mob should appear for a block hit: the block next to the clicked face. */
function besideFace(block, face) {
  const l = block.location;
  const off = { Up: [0, 1, 0], Down: [0, -1, 0], North: [0, 0, -1], South: [0, 0, 1], East: [1, 0, 0], West: [-1, 0, 0] };
  const [dx, dy, dz] = off[face] ?? [0, 1, 0];
  return { x: l.x + dx, y: l.y + dy, z: l.z + dz };
}

// --- Capture by right-clicking the mob: cancel the normal interaction (sit / feed / trade) ---
world.beforeEvents.playerInteractWithEntity.subscribe((ev) => {
  const orb = BY_EMPTY.get(ev.itemStack?.typeId);
  if (!orb || !ev.target || ev.target.typeId === "minecraft:player") return;
  ev.cancel = true;
  const { player, target } = ev;
  system.run(() => {
    if (!onCooldown(player)) capture(player, orb, target);
  });
});

// --- Release on a block ----------------------------------------------------------------
world.beforeEvents.playerInteractWithBlock.subscribe((ev) => {
  const orb = BY_FULL.get(ev.itemStack?.typeId);
  if (!orb || !ev.isFirstEvent) return;
  ev.cancel = true;
  const { player, block, blockFace } = ev;
  const loc = besideFace(block, blockFace);
  system.run(() => {
    if (!onCooldown(player)) release(player, orb, loc);
  });
});

// --- Using an orb in the air: aim at a mob (capture) or at a block further away (release) ---
world.afterEvents.itemUse.subscribe((ev) => {
  const player = ev.source;
  const id = ev.itemStack?.typeId;
  const emptyOrb = BY_EMPTY.get(id);
  const fullOrbKind = BY_FULL.get(id);
  if (!emptyOrb && !fullOrbKind) return;
  if (onCooldown(player)) return;
  if (emptyOrb) {
    const hit = player
      .getEntitiesFromViewDirection({ maxDistance: CAPTURE_RANGE })
      .find((h) => h.entity?.isValid && h.entity.typeId !== "minecraft:player");
    if (hit) capture(player, emptyOrb, hit.entity);
    else tell(player, emptyOrb.aimHint);
  } else {
    const hit = player.getBlockFromViewDirection({ maxDistance: RELEASE_RANGE });
    if (hit) release(player, fullOrbKind, besideFace(hit.block, hit.face));
    else tell(player, "§7Aim at the ground to let it out.");
  }
});
