// Laser pointer for Big Cats. Hand-written (not generated) - edit freely.
//
// Use (right-click / tap) the mymod:laser_pointer item: a raycast from the player's eyes
// finds the block surface they look at (up to LASER_RANGE blocks) and a mymod:laser_dot
// entity is spawned there, or moved there if the player already has one.
// Big Cats chase the dot through their behavior JSON (they "attack" the bigcat_laser_dot
// family with ocelotattack + leap_at_target, i.e. stalk and pounce; the dot takes no damage).
// This script only places, moves, lights up and removes dots, and makes cats lose interest.
//
// The dot disappears DOT_TIMEOUT_TICKS after the last use, as soon as the player stops
// holding the pointer, or when the laser is pointed at the sky.
// Dots are never meant to survive a reload: any dot not owned by this script session is
// removed by the sweep below.

import { world, system, EquipmentSlot } from "@minecraft/server";
import "./cat_orb.js"; // Cat Orb: capture and release Big Cats

const POINTER_ID = "mymod:laser_pointer";
const DOT_ID = "mymod:laser_dot";
const CAT_ID = "mymod:big_cat";
const GLOW_PARTICLE = "mymod:laser_dot_glow";
const BORED_TAG = "bigcat_bored";

const LASER_RANGE = 32; // blocks
const DOT_TIMEOUT_TICKS = 100; // 5 s after the last use
const USE_COOLDOWN_TICKS = 3; // also de-duplicates itemUse + playerInteractWithBlock
const GLOW_INTERVAL_TICKS = 2;
const SWEEP_INTERVAL_TICKS = 20;
const BORED_CHECK_RADIUS = 4; // cats this close to the dot may lose interest...
const BORED_CHANCE = 0.04; // ...with this chance per cat per second
const BORED_MIN_TICKS = 60;
const BORED_MAX_TICKS = 160;
const DIMENSIONS = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"];

/** playerId -> { player, dot, dimensionId, glowAt, lastUse } */
const lasers = new Map();
/** playerId -> tick of last accepted use */
const lastUseTick = new Map();
/** catId -> tick when the cat gets interested again */
const boredUntil = new Map();

const NORMALS = {
  Up: { x: 0, y: 1, z: 0 },
  Down: { x: 0, y: -1, z: 0 },
  North: { x: 0, y: 0, z: -1 },
  South: { x: 0, y: 0, z: 1 },
  East: { x: 1, y: 0, z: 0 },
  West: { x: -1, y: 0, z: 0 },
};

function isHoldingPointer(player) {
  try {
    const item = player.getComponent("minecraft:equippable")?.getEquipment(EquipmentSlot.Mainhand);
    return item?.typeId === POINTER_ID;
  } catch {
    return false;
  }
}

/** World position of the raycast hit (faceLocation is documented as block-relative). */
function hitPoint(hit) {
  const b = hit.block.location;
  const f = hit.faceLocation;
  const relative = Math.abs(f.x) <= 1.01 && Math.abs(f.y) <= 1.01 && Math.abs(f.z) <= 1.01;
  return relative ? { x: b.x + f.x, y: b.y + f.y, z: b.z + f.z } : { x: f.x, y: f.y, z: f.z };
}

function removeLaser(playerId) {
  const laser = lasers.get(playerId);
  lasers.delete(playerId);
  if (laser?.dot?.isValid) {
    try {
      laser.dot.remove();
    } catch (e) {
      console.warn(`[bigcat laser] could not remove dot: ${e}`);
    }
  }
}

function pointLaser(player) {
  const now = system.currentTick;
  if (now - (lastUseTick.get(player.id) ?? -1000) < USE_COOLDOWN_TICKS) return;
  lastUseTick.set(player.id, now);

  const hit = player.getBlockFromViewDirection({
    maxDistance: LASER_RANGE,
    includeLiquidBlocks: false,
    includePassableBlocks: false,
  });
  if (!hit) {
    removeLaser(player.id); // pointed at the sky: no dot
    return;
  }

  const n = NORMALS[hit.face] ?? NORMALS.Up;
  const p = hitPoint(hit);
  // The dot model is a 4px (0.25 block) cube standing on the entity origin: sit on floors,
  // hang under ceilings, and sit against walls centred on the hit point.
  const DOT_SIZE = 0.25;
  const out = n.y === 0 ? DOT_SIZE / 2 + 0.01 : 0.01;
  const dotLoc = {
    x: p.x + n.x * out,
    y: p.y + n.y * out - (n.y < 0 ? DOT_SIZE : n.y === 0 ? DOT_SIZE / 2 : 0),
    z: p.z + n.z * out,
  };
  // Glow halo centred on the cube, so it shows around the dot instead of inside it.
  const c = DOT_SIZE / 2 + 0.01;
  const glowAt = { x: p.x + n.x * c, y: p.y + n.y * c, z: p.z + n.z * c };
  const dim = player.dimension;

  let laser = lasers.get(player.id);
  if (laser && (!laser.dot?.isValid || laser.dimensionId !== dim.id)) {
    removeLaser(player.id);
    laser = undefined;
  }
  try {
    if (laser) {
      laser.dot.teleport(dotLoc);
    } else {
      const dot = dim.spawnEntity(DOT_ID, dotLoc);
      laser = { player, dot, dimensionId: dim.id };
      lasers.set(player.id, laser);
    }
    laser.glowAt = glowAt;
    laser.lastUse = now;
    player.playSound("random.click", { pitch: 2.0, volume: 0.25 });
  } catch (e) {
    console.warn(`[bigcat laser] could not place dot: ${e}`);
  }
}

// Right-click / tap in the air (or at a far block).
world.afterEvents.itemUse.subscribe((ev) => {
  if (ev.itemStack?.typeId === POINTER_ID) pointLaser(ev.source);
});

// Right-click / tap on a block within reach (itemUse may not fire then). Holding the
// button repeats this event, which lets the player drag the dot across nearby blocks.
world.afterEvents.playerInteractWithBlock.subscribe((ev) => {
  if (ev.itemStack?.typeId === POINTER_ID) pointLaser(ev.player);
});

world.afterEvents.playerLeave.subscribe((ev) => {
  removeLaser(ev.playerId);
  lastUseTick.delete(ev.playerId);
});

// Glow + expiry.
system.runInterval(() => {
  const now = system.currentTick;
  for (const [playerId, laser] of [...lasers]) {
    const p = laser.player;
    if (
      !p.isValid ||
      !laser.dot?.isValid ||
      now - laser.lastUse > DOT_TIMEOUT_TICKS ||
      p.dimension.id !== laser.dimensionId ||
      !isHoldingPointer(p)
    ) {
      removeLaser(playerId);
      continue;
    }
    try {
      laser.dot.dimension.spawnParticle(GLOW_PARTICLE, laser.glowAt);
    } catch {
      // chunk unloaded or similar; the dot will be cleaned up by the checks above
    }
  }
}, GLOW_INTERVAL_TICKS);

// Orphan sweep (dots left over from a reload or a crash) + cats losing interest.
system.runInterval(() => {
  const now = system.currentTick;
  const owned = new Set();
  for (const laser of lasers.values()) if (laser.dot?.isValid) owned.add(laser.dot.id);

  for (const dimId of DIMENSIONS) {
    let dim;
    try {
      dim = world.getDimension(dimId);
    } catch {
      continue;
    }
    for (const dot of dim.getEntities({ type: DOT_ID })) {
      if (!owned.has(dot.id)) {
        try {
          dot.remove();
        } catch {}
      }
    }
    // Tags are saved with the cat: clear any bored tag we are no longer tracking.
    for (const cat of dim.getEntities({ type: CAT_ID, tags: [BORED_TAG] })) {
      const until = boredUntil.get(cat.id);
      if (until === undefined || now >= until) {
        cat.removeTag(BORED_TAG);
        boredUntil.delete(cat.id);
      }
    }
  }

  // Cats that have been batting at the dot may get bored for a few seconds.
  for (const laser of lasers.values()) {
    if (!laser.dot?.isValid) continue;
    const cats = laser.dot.dimension.getEntities({
      type: CAT_ID,
      location: laser.dot.location,
      maxDistance: BORED_CHECK_RADIUS,
      excludeTags: [BORED_TAG],
    });
    for (const cat of cats) {
      if (Math.random() < BORED_CHANCE) {
        cat.addTag(BORED_TAG);
        boredUntil.set(cat.id, now + BORED_MIN_TICKS + Math.floor(Math.random() * (BORED_MAX_TICKS - BORED_MIN_TICKS)));
      }
    }
  }
}, SWEEP_INTERVAL_TICKS);
