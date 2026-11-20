// Player Trap Orb: "catch" another player and let them out again. Hand-written (not generated).
//
// The game can't put a player into a structure the way orbs.js does with mobs, so this is a
// pretend capture:
//   * Trap: use an empty mymod:trap_orb on a player (aim at them within TRAP_RANGE and use,
//     or hit them with it). They're switched to spectator mode with movement turned off and
//     held in place high above where they stood. Your orb becomes mymod:trap_orb_full.
//   * Release: use the full orb on a block (or aim at one within RELEASE_RANGE). They come back
//     there, in their old game mode, able to move again. You get the empty orb back.
//
// Safety: a trapped player is always freed (back where they were caught) when
//   * MAX_TRAP_MS passes,
//   * the person holding them leaves the world,
//   * or the world reloads while the holder is away.
// Every trap is stored as a world dynamic property (bigcat_trap_<playerId>), so it survives
// reloads and a trapped player who logs out is sorted out when they come back.

import { world, system, ItemStack, GameMode, InputPermissionCategory } from "@minecraft/server";

const TRAP_EMPTY = "mymod:trap_orb";
const TRAP_FULL = "mymod:trap_orb_full";
const PROP_TARGET = "bigcat_trap_target"; // on the full orb: trapped player's id
const PROP_TARGET_NAME = "bigcat_trap_name"; // on the full orb: their name
const RECORD_PREFIX = "bigcat_trap_"; // world dynamic property per trapped player

const TRAP_RANGE = 10;
const RELEASE_RANGE = 8;
const MAX_TRAP_MS = 5 * 60 * 1000; // freed automatically after 5 minutes
const WATCH_INTERVAL = 10; // ticks
const COOLDOWN_TICKS = 6;
const LOCKED = [
  InputPermissionCategory.Movement,
  InputPermissionCategory.Jump,
  InputPermissionCategory.Sneak,
  InputPermissionCategory.Mount,
  InputPermissionCategory.Dismount,
];

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

// --- trap records ------------------------------------------------------------------------
function getRecord(playerId) {
  const raw = world.getDynamicProperty(RECORD_PREFIX + playerId);
  if (typeof raw !== "string") return undefined;
  try {
    return JSON.parse(raw);
  } catch {
    return undefined;
  }
}

function setRecord(playerId, rec) {
  world.setDynamicProperty(RECORD_PREFIX + playerId, rec ? JSON.stringify(rec) : undefined);
}

function allRecordIds() {
  return world
    .getDynamicPropertyIds()
    .filter((k) => k.startsWith(RECORD_PREFIX))
    .map((k) => k.slice(RECORD_PREFIX.length));
}

function onlinePlayer(id) {
  return world.getAllPlayers().find((p) => p.id === id);
}

function lockMovement(player, locked) {
  for (const cat of LOCKED) {
    try {
      player.inputPermissions.setPermissionCategory(cat, !locked);
    } catch {}
  }
}

/** Put a trapped player back: old game mode, movement on, at `to` (or where they were caught). */
function free(player, rec, to, why) {
  setRecord(player.id, undefined);
  lockMovement(player, false);
  try {
    player.setGameMode(rec.prevMode ?? GameMode.Survival);
  } catch {}
  const dest = to ?? rec.origin;
  try {
    player.teleport({ x: dest.x, y: dest.y, z: dest.z }, { dimension: world.getDimension(dest.dim) });
  } catch (e) {
    console.warn(`[bigcat trap] could not move ${player.name} back: ${e}`);
  }
  player.onScreenDisplay.setTitle("§aYou're free!", { subtitle: why, fadeInDuration: 5, stayDuration: 40, fadeOutDuration: 10 });
}

// --- trap / release ----------------------------------------------------------------------
function trap(holder, target) {
  if (!target?.isValid || target.typeId !== "minecraft:player") return;
  const held = heldSlot(holder, TRAP_EMPTY);
  if (!held) return;
  if (target.id === holder.id) {
    tell(holder, "§7You can't trap yourself.");
    return;
  }
  if (getRecord(target.id)) {
    tell(holder, `§7${target.name} is already trapped.`);
    return;
  }

  const dim = target.dimension;
  const o = target.location;
  const cell = { x: Math.floor(o.x) + 0.5, y: dim.heightRange.max - 2, z: Math.floor(o.z) + 0.5 };
  const rec = {
    holderId: holder.id,
    holderName: holder.name,
    prevMode: target.getGameMode(),
    origin: { x: o.x, y: o.y, z: o.z, dim: dim.id },
    cell: { ...cell, dim: dim.id },
    until: Date.now() + MAX_TRAP_MS,
  };
  setRecord(target.id, rec);
  try {
    target.setGameMode(GameMode.Spectator);
    lockMovement(target, true);
    target.teleport(cell, { dimension: dim });
  } catch (e) {
    console.warn(`[bigcat trap] trap failed: ${e}`);
    free(target, rec, undefined, "The trap fizzled.");
    tell(holder, "§cThe trap fizzled.");
    return;
  }

  const s = new ItemStack(TRAP_FULL, 1);
  s.setDynamicProperty(PROP_TARGET, target.id);
  s.setDynamicProperty(PROP_TARGET_NAME, target.name);
  s.nameTag = `Player Trap Orb: ${target.name}`;
  s.setLore([`§7Holds §f${target.name}`, "§7Freed automatically after 5 minutes"]);
  giveBack(holder, held, s);

  dim.spawnParticle("minecraft:basic_portal_particle", { x: o.x, y: o.y + 1, z: o.z });
  holder.playSound("mob.shulker.close", { pitch: 0.8 });
  target.playSound("mob.shulker.close", { pitch: 0.8 });
  target.onScreenDisplay.setTitle("§cTrapped!", {
    subtitle: `${holder.name} caught you in an orb`,
    fadeInDuration: 5,
    stayDuration: 60,
    fadeOutDuration: 10,
  });
  tell(holder, `§dTrapped ${target.name}!`);
}

function release(holder, location) {
  const held = heldSlot(holder, TRAP_FULL);
  if (!held) return;
  const targetId = held.item.getDynamicProperty(PROP_TARGET);
  const name = held.item.getDynamicProperty(PROP_TARGET_NAME) ?? "them";
  held.container.setItem(held.slot, new ItemStack(TRAP_EMPTY, 1));

  const rec = typeof targetId === "string" ? getRecord(targetId) : undefined;
  if (!rec) {
    tell(holder, `§7${name} already escaped.`);
    return;
  }
  const to = { x: location.x + 0.5, y: location.y, z: location.z + 0.5, dim: holder.dimension.id };
  const target = onlinePlayer(targetId);
  if (!target) {
    // They logged out while trapped: free them here when they come back.
    setRecord(targetId, { ...rec, releaseTo: to });
    tell(holder, `§7${name} is offline. They'll appear here when they return.`);
    return;
  }
  free(target, rec, to, `${holder.name} let you out.`);
  holder.dimension.spawnParticle("minecraft:basic_portal_particle", { x: to.x, y: to.y + 1, z: to.z });
  holder.playSound("random.pop", { pitch: 0.8 });
  tell(holder, `§dReleased ${name}!`);
}

function besideFace(block, face) {
  const l = block.location;
  const off = { Up: [0, 1, 0], Down: [0, -1, 0], North: [0, 0, -1], South: [0, 0, 1], East: [1, 0, 0], West: [-1, 0, 0] };
  const [dx, dy, dz] = off[face] ?? [0, 1, 0];
  return { x: l.x + dx, y: l.y + dy, z: l.z + dz };
}

// --- events ------------------------------------------------------------------------------
// Use in the air: aim at a player (trap) or a block (release).
world.afterEvents.itemUse.subscribe((ev) => {
  const p = ev.source;
  const id = ev.itemStack?.typeId;
  if (id !== TRAP_EMPTY && id !== TRAP_FULL) return;
  if (onCooldown(p)) return;
  if (id === TRAP_EMPTY) {
    const hit = p
      .getEntitiesFromViewDirection({ maxDistance: TRAP_RANGE })
      .find((h) => h.entity?.typeId === "minecraft:player" && h.entity.id !== p.id);
    if (hit) trap(p, hit.entity);
    else tell(p, "§7Aim at another player to trap them.");
  } else {
    const hit = p.getBlockFromViewDirection({ maxDistance: RELEASE_RANGE });
    if (hit) release(p, besideFace(hit.block, hit.face));
    else tell(p, "§7Aim at the ground to let them out.");
  }
});

// Hitting a player with the empty orb also traps them.
world.afterEvents.entityHitEntity.subscribe((ev) => {
  const p = ev.damagingEntity;
  if (p?.typeId !== "minecraft:player" || ev.hitEntity?.typeId !== "minecraft:player") return;
  if (!heldSlot(p, TRAP_EMPTY) || onCooldown(p)) return;
  trap(p, ev.hitEntity);
});

// Right-clicking a block with the full orb releases there.
world.beforeEvents.playerInteractWithBlock.subscribe((ev) => {
  if (ev.itemStack?.typeId !== TRAP_FULL || !ev.isFirstEvent) return;
  ev.cancel = true;
  const { player, block, blockFace } = ev;
  const loc = besideFace(block, blockFace);
  system.run(() => {
    if (!onCooldown(player)) release(player, loc);
  });
});

// Watchdog: keep trapped players in place, and free them when the trap runs out.
system.runInterval(() => {
  const now = Date.now();
  for (const id of allRecordIds()) {
    const rec = getRecord(id);
    const target = onlinePlayer(id);
    if (!rec) {
      setRecord(id, undefined);
      continue;
    }
    if (!target) continue; // offline: handled when they come back
    if (rec.releaseTo) {
      free(target, rec, rec.releaseTo, `${rec.holderName} let you out.`);
    } else if (now > rec.until) {
      free(target, rec, undefined, "The trap wore off.");
    } else if (!onlinePlayer(rec.holderId)) {
      free(target, rec, undefined, `${rec.holderName} left the world.`);
    } else {
      // still trapped: make sure they stay put
      if (target.getGameMode() !== GameMode.Spectator) target.setGameMode(GameMode.Spectator);
      lockMovement(target, true);
      const l = target.location;
      const c = rec.cell;
      if (target.dimension.id !== c.dim || Math.abs(l.x - c.x) + Math.abs(l.y - c.y) + Math.abs(l.z - c.z) > 1) {
        target.teleport({ x: c.x, y: c.y, z: c.z }, { dimension: world.getDimension(c.dim) });
      }
      const left = Math.ceil((rec.until - now) / 1000);
      tell(target, `§cTrapped by ${rec.holderName} §7(free in ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")})`);
    }
  }
}, WATCH_INTERVAL);

