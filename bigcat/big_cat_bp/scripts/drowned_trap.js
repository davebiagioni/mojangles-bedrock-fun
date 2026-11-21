// Drowned Trap. Hand-written (not generated) - edit freely.
//
// Use the mymod:drowned_trap item on a block (it can be the sea floor; aiming through water is
// fine) to place a mymod:drowned_lure: a little cage with a fish in it.
// Drowned treat the lure as an enemy (tools/gen_drowned_trap.py adds it to the vanilla drowned's
// attack targets; no other mob gets that change). When a drowned hits the lure, throws a trident
// at it, or gets right up against it:
//   * the drowned "explodes": explosion flash and sound only, nothing else is hurt, no blocks break,
//   * it vanishes without its normal loot, and drops ONE weapon with random enchantments
//     instead: its own trident if it was holding one, otherwise a random weapon from WEAPONS.
// The trap keeps working, drowned after drowned. Hit it to pick it back up.

import { world, system, ItemStack, EquipmentSlot, EnchantmentTypes } from "@minecraft/server";

const TRAP_ITEM = "mymod:drowned_trap";
const LURE_ID = "mymod:drowned_lure";
const DROWNED_ID = "minecraft:drowned";

const PLACE_RANGE = 8; // blocks
const COOLDOWN_TICKS = 5; // also de-duplicates itemUse + playerInteractWithBlock
const CHECK_INTERVAL_TICKS = 5;
const CONTACT_RADIUS = 1.6; // a drowned this close to the lure gets caught even if no hit registered
const NOTIFY_RADIUS = 32; // players this close hear about each catch
const DIMENSIONS = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"];

// [item id, weight]. Tridents are the most likely; it's a drowned, after all.
const WEAPONS = [
  ["minecraft:trident", 4],
  ["minecraft:iron_sword", 3],
  ["minecraft:diamond_sword", 2],
  ["minecraft:iron_axe", 2],
  ["minecraft:diamond_axe", 1],
  ["minecraft:bow", 2],
  ["minecraft:crossbow", 2],
];
const MIN_ENCHANTS = 1;
const MAX_ENCHANTS = 3;
const CURSES = new Set(["binding", "vanishing"]);

/** playerId -> tick of last accepted use */
const lastUse = new Map();
/** ids of drowned already caught (an explosion can be reported by several events in one tick) */
const caught = new Set();

function safe(fn) {
  try {
    return fn();
  } catch {
    return undefined;
  }
}

const randInt = (lo, hi) => lo + Math.floor(Math.random() * (hi - lo + 1));

function pickWeighted(list) {
  let r = Math.random() * list.reduce((s, [, w]) => s + w, 0);
  for (const [id, w] of list) {
    r -= w;
    if (r < 0) return id;
  }
  return list[list.length - 1][0];
}

function shuffled(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/** A new `itemId` with MIN..MAX random enchantments that fit it (no curses, no clashes). */
function enchantedWeapon(itemId) {
  const stack = new ItemStack(itemId, 1);
  const ench = stack.getComponent("minecraft:enchantable");
  if (!ench) return stack;
  let want = randInt(MIN_ENCHANTS, MAX_ENCHANTS);
  for (const type of shuffled(EnchantmentTypes.getAll())) {
    if (want <= 0) break;
    if (CURSES.has(type.id.replace("minecraft:", ""))) continue;
    const e = { type, level: randInt(1, type.maxLevel) };
    try {
      if (ench.canAddEnchantment(e)) {
        ench.addEnchantment(e);
        want--;
      }
    } catch {
      // doesn't apply to this item or clashes with one it already has
    }
  }
  return stack;
}

function heldWeaponId(drowned) {
  // Reading a mob's hands may not be supported on every version; fall back to a random weapon.
  const held = safe(() => drowned.getComponent("minecraft:equippable")?.getEquipment(EquipmentSlot.Mainhand));
  return held?.typeId === "minecraft:trident" ? "minecraft:trident" : undefined;
}

// --- catching ---------------------------------------------------------------------------------
function explode(drowned) {
  if (!drowned?.isValid || drowned.typeId !== DROWNED_ID || caught.has(drowned.id)) return;
  caught.add(drowned.id);
  const dim = drowned.dimension;
  const at = { ...drowned.location, y: drowned.location.y + 0.8 };
  const weapon = enchantedWeapon(heldWeaponId(drowned) ?? pickWeighted(WEAPONS));
  safe(() => dim.spawnParticle("minecraft:huge_explosion_emitter", at));
  safe(() => dim.playSound("random.explode", at, { volume: 1.0, pitch: 1.1 }));
  // remove() rather than kill(): no normal loot, only the weapon
  safe(() => drowned.remove());
  safe(() => dim.spawnItem(weapon, at));
  for (const p of dim.getPlayers({ location: at, maxDistance: NOTIFY_RADIUS })) {
    p.onScreenDisplay.setActionBar("§bDrowned Trap: §fcaught a drowned!");
  }
  system.runTimeout(() => caught.delete(drowned.id), 20);
}

world.afterEvents.entityHitEntity.subscribe((ev) => {
  const { damagingEntity: by, hitEntity: hit } = ev;
  if (hit?.typeId !== LURE_ID) return;
  if (by?.typeId === DROWNED_ID) explode(by);
  else if (by?.typeId === "minecraft:player") pickUp(by, hit);
});

world.afterEvents.projectileHitEntity.subscribe((ev) => {
  const hit = safe(() => ev.getEntityHit().entity);
  if (hit?.typeId === LURE_ID && ev.source?.typeId === DROWNED_ID) explode(ev.source);
});

// Backup in case a hit doesn't register (e.g. the drowned is pushing against it): close contact counts.
system.runInterval(() => {
  for (const dimId of DIMENSIONS) {
    const dim = safe(() => world.getDimension(dimId));
    const lures = safe(() => dim.getEntities({ type: LURE_ID })) ?? [];
    for (const lure of lures) {
      const near = safe(() => dim.getEntities({ type: DROWNED_ID, location: lure.location, maxDistance: CONTACT_RADIUS }));
      for (const d of near ?? []) explode(d);
    }
  }
}, CHECK_INTERVAL_TICKS);

// --- placing and picking up -----------------------------------------------------------------------
function besideFace(block, face) {
  const off = { Up: [0, 1, 0], Down: [0, -1, 0], North: [0, 0, -1], South: [0, 0, 1], East: [1, 0, 0], West: [-1, 0, 0] };
  const [dx, dy, dz] = off[face] ?? [0, 1, 0];
  const l = block.location;
  return { x: l.x + dx + 0.5, y: l.y + dy, z: l.z + dz + 0.5 };
}

function useOneFromHand(player) {
  const container = player.getComponent("minecraft:inventory")?.container;
  const slot = player.selectedSlotIndex;
  const item = container?.getItem(slot);
  if (item?.typeId !== TRAP_ITEM) return false;
  if (item.amount > 1) {
    item.amount -= 1;
    container.setItem(slot, item);
  } else {
    container.setItem(slot, undefined);
  }
  return true;
}

/** `clicked` ({ block, face }) when the player clicked a block within reach; else we raycast. */
function place(player, clicked) {
  const now = system.currentTick;
  if (now - (lastUse.get(player.id) ?? -1000) < COOLDOWN_TICKS) return;
  lastUse.set(player.id, now);
  const hit = clicked ?? player.getBlockFromViewDirection({ maxDistance: PLACE_RANGE });
  if (!hit) {
    player.onScreenDisplay.setActionBar("§7Aim at a block (the sea floor works) to place the trap.");
    return;
  }
  if (!useOneFromHand(player)) return;
  const at = besideFace(hit.block, hit.face);
  try {
    player.dimension.spawnEntity(LURE_ID, at);
  } catch {
    player.dimension.spawnItem(new ItemStack(TRAP_ITEM, 1), player.location); // give it back
    return;
  }
  player.dimension.playSound("random.anvil_land", at, { volume: 0.4, pitch: 1.6 });
}

function pickUp(player, lure) {
  const at = lure.location;
  safe(() => lure.remove());
  const leftover = player.getComponent("minecraft:inventory")?.container?.addItem(new ItemStack(TRAP_ITEM, 1));
  if (leftover) player.dimension.spawnItem(leftover, at);
  player.dimension.playSound("random.pop", at);
}

world.afterEvents.itemUse.subscribe((ev) => {
  if (ev.itemStack?.typeId === TRAP_ITEM && ev.source?.typeId === "minecraft:player") place(ev.source);
});

// Clicking a block within reach doesn't fire itemUse. The after-event only fires when the click
// actually did something, which a plain floor block never does for this item, so use the
// before-event (like orbs.js) and place on the next tick. Holding the button repeats it.
world.beforeEvents.playerInteractWithBlock.subscribe((ev) => {
  if (!ev.isFirstEvent || ev.itemStack?.typeId !== TRAP_ITEM) return;
  ev.cancel = true;
  const { player, block, blockFace } = ev;
  system.run(() => place(player, { block, face: blockFace }));
});

world.afterEvents.playerLeave.subscribe((ev) => lastUse.delete(ev.playerId));
