// Cat Orb: capture a Big Cat into an item and release it again later. Hand-written (not generated).
//
// Capture: use an empty mymod:cat_orb on a Big Cat (right-click it, or aim at it within
//   CAPTURE_RANGE blocks and use). The cat is saved, with everything about it (coat, owner,
//   collar colour, name, age, health), into a world structure, and removed. The orb in your hand
//   becomes a mymod:cat_orb_full that remembers which structure holds the cat.
// Release: use the occupied orb on a block (or aim at one within RELEASE_RANGE). The structure
//   is placed there, entities only, so the same cat comes back, and is then deleted. You get the
//   empty orb back.
//
// Before saving, the cat is teleported into an empty spot high above itself, so the 1-block
// structure holds only that cat and never another mob that happened to stand in the same block.

import { world, system, ItemStack, StructureSaveMode } from "@minecraft/server";

const EMPTY_ORB = "mymod:cat_orb";
const FULL_ORB = "mymod:cat_orb_full";
const CAT_ID = "mymod:big_cat";
const COAT_PROPERTY = "mymod:coat";

const PROP_STRUCTURE = "bigcat_orb_structure"; // on the full orb: structure id
const PROP_CAT_NAME = "bigcat_orb_name"; // on the full orb: name shown in messages

const CAPTURE_RANGE = 8; // blocks, when aiming instead of clicking the cat
const RELEASE_RANGE = 8;
const COOLDOWN_TICKS = 6; // one click can fire both a before-event and itemUse

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

/** Put `stack` in the held slot if that slot is about to be empty, else in the inventory / at the feet. */
function giveBack(player, held, stack) {
  if (held.item.amount <= 1) {
    held.container.setItem(held.slot, stack);
    return;
  }
  held.item.amount -= 1;
  held.container.setItem(held.slot, held.item);
  const leftover = held.container.addItem(stack);
  if (leftover) player.dimension.spawnItem(leftover, player.location);
}

function emptyOrb() {
  return new ItemStack(EMPTY_ORB, 1);
}

function fullOrb(label, coat, tamed, structureId) {
  const s = new ItemStack(FULL_ORB, 1);
  s.setDynamicProperty(PROP_STRUCTURE, structureId);
  s.setDynamicProperty(PROP_CAT_NAME, label);
  s.nameTag = `Cat Orb: ${label}`;
  const lore = [`§7Holds §f${label}`];
  if (typeof coat === "number") lore.push(`§7Coat §f${String(coat).padStart(3, "0")}`);
  lore.push(tamed ? "§aTamed" : "§eWild");
  s.setLore(lore);
  return s;
}

function catLabel(cat) {
  if (cat.nameTag) return cat.nameTag;
  const coat = cat.getProperty(COAT_PROPERTY);
  return typeof coat === "number" ? `Big Cat (coat ${String(coat).padStart(3, "0")})` : "Big Cat";
}

function capture(player, cat) {
  if (!cat?.isValid || cat.typeId !== CAT_ID) return;
  const held = heldSlot(player, EMPTY_ORB);
  if (!held) return;

  const tameable = cat.getComponent("minecraft:tameable");
  if (tameable?.isTamed && tameable.tamedToPlayerId && tameable.tamedToPlayerId !== player.id) {
    tell(player, "§cThat cat belongs to someone else.");
    return;
  }

  const dim = cat.dimension;
  const label = catLabel(cat);
  const tamed = !!tameable?.isTamed;
  const coat = cat.getProperty(COAT_PROPERTY);
  const from = cat.location;

  // Isolate the cat in an empty block near the top of the world, straight above itself.
  const top = dim.heightRange.max - 3;
  const spot = { x: Math.floor(from.x), y: top, z: Math.floor(from.z) };
  const structureId = `mymod:cat_orb_${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`;
  try {
    cat.teleport({ x: spot.x + 0.5, y: spot.y + 0.5, z: spot.z + 0.5 });
  } catch (e) {
    console.warn(`[bigcat orb] could not move the cat: ${e}`);
    tell(player, "§cThe orb fizzled. The cat is still there.");
    return;
  }

  // Save one tick later, once the move has certainly happened, and only if the cat is
  // really in the spot. The cat is deleted only after the save succeeded.
  system.runTimeout(() => {
    const putBack = (msg) => {
      try {
        if (cat.isValid) cat.teleport(from);
      } catch {}
      tell(player, msg);
    };
    if (!cat.isValid) return;
    const l = cat.location;
    if (Math.floor(l.x) !== spot.x || Math.floor(l.y) !== spot.y || Math.floor(l.z) !== spot.z) {
      putBack("§cThe cat slipped away. Try again.");
      return;
    }
    const heldNow = heldSlot(player, EMPTY_ORB);
    if (!heldNow) {
      putBack("§7Hold the Cat Orb to catch a cat.");
      return;
    }
    try {
      world.structureManager.createFromWorld(structureId, dim, spot, spot, {
        includeBlocks: false,
        includeEntities: true,
        saveMode: StructureSaveMode.World,
      });
    } catch (e) {
      console.warn(`[bigcat orb] capture failed: ${e}`);
      putBack("§cThe orb fizzled. The cat is still there.");
      return;
    }
    cat.remove();
    giveBack(player, heldNow, fullOrb(label, coat, tamed, structureId));
    dim.spawnParticle("minecraft:basic_portal_particle", { x: from.x, y: from.y + 1, z: from.z });
    dim.spawnParticle("minecraft:villager_happy", { x: from.x, y: from.y + 1.5, z: from.z });
    player.playSound("mob.shulker.close", { pitch: 1.4 });
    tell(player, `§dCaught ${label}!`);
  }, 1);
}

function release(player, location) {
  const held = heldSlot(player, FULL_ORB);
  if (!held) return;
  const structureId = held.item.getDynamicProperty(PROP_STRUCTURE);
  const label = held.item.getDynamicProperty(PROP_CAT_NAME) ?? "your cat";

  const structure = typeof structureId === "string" ? world.structureManager.get(structureId) : undefined;
  if (!structure) {
    tell(player, "§cThis orb is empty. Its cat could not be found.");
    held.container.setItem(held.slot, emptyOrb());
    return;
  }
  try {
    world.structureManager.place(structure, player.dimension, location, {
      includeBlocks: false,
      includeEntities: true,
    });
  } catch (e) {
    console.warn(`[bigcat orb] release failed: ${e}`);
    tell(player, "§cThe cat can't come out here. Try somewhere else.");
    return;
  }
  try {
    world.structureManager.delete(structureId);
  } catch (e) {
    console.warn(`[bigcat orb] could not delete structure ${structureId}: ${e}`);
  }
  held.container.setItem(held.slot, emptyOrb());

  const c = { x: location.x + 0.5, y: location.y + 1, z: location.z + 0.5 };
  player.dimension.spawnParticle("minecraft:basic_portal_particle", c);
  player.dimension.spawnParticle("minecraft:heart_particle", { x: c.x, y: c.y + 1.5, z: c.z });
  player.playSound("random.pop", { pitch: 0.8 });
  player.playSound("mob.cat.meow");
  tell(player, `§dWelcome back, ${label}!`);
}

/** Where a released cat should appear for a block hit: the block next to the clicked face. */
function besideFace(block, face) {
  const l = block.location;
  const off = { Up: [0, 1, 0], Down: [0, -1, 0], North: [0, 0, -1], South: [0, 0, 1], East: [1, 0, 0], West: [-1, 0, 0] };
  const [dx, dy, dz] = off[face] ?? [0, 1, 0];
  return { x: l.x + dx, y: l.y + dy, z: l.z + dz };
}

// --- Capture -------------------------------------------------------------------------
// Right-clicking the cat: cancel the normal interaction (sit / feed / tame) and capture.
world.beforeEvents.playerInteractWithEntity.subscribe((ev) => {
  if (ev.itemStack?.typeId !== EMPTY_ORB || ev.target?.typeId !== CAT_ID) return;
  ev.cancel = true;
  const { player, target } = ev;
  system.run(() => {
    if (!onCooldown(player)) capture(player, target);
  });
});

// --- Release on a block ----------------------------------------------------------------
world.beforeEvents.playerInteractWithBlock.subscribe((ev) => {
  if (ev.itemStack?.typeId !== FULL_ORB || !ev.isFirstEvent) return;
  ev.cancel = true;
  const { player, block, blockFace } = ev;
  const loc = besideFace(block, blockFace);
  system.run(() => {
    if (!onCooldown(player)) release(player, loc);
  });
});

// --- Using the orb in the air: aim at a cat (capture) or at a block further away (release) ---
world.afterEvents.itemUse.subscribe((ev) => {
  const player = ev.source;
  const id = ev.itemStack?.typeId;
  if (id !== EMPTY_ORB && id !== FULL_ORB) return;
  if (onCooldown(player)) return;
  if (id === EMPTY_ORB) {
    const hit = player
      .getEntitiesFromViewDirection({ maxDistance: CAPTURE_RANGE })
      .find((h) => h.entity?.typeId === CAT_ID);
    if (hit) capture(player, hit.entity);
    else tell(player, "§7Aim at a Big Cat to catch it.");
  } else {
    const hit = player.getBlockFromViewDirection({ maxDistance: RELEASE_RANGE });
    if (hit) release(player, besideFace(hit.block, hit.face));
    else tell(player, "§7Aim at the ground to let your cat out.");
  }
});
