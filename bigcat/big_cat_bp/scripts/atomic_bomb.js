// Atomic Bomb. Hand-written (not generated) - edit freely.
//
// mymod:atomic_bomb is a block (blocks/atomic_bomb.json). Light it with flint and steel or a fire
// charge, power it with redstone, or blow it up with another explosion (that one has a short fuse).
// Then:
//   * FUSE_SECONDS countdown: beeps that get faster and higher, smoke, and a countdown on the
//     action bar of everyone within WARN_RADIUS. Break the bomb during the countdown to defuse it.
//   * BOOM: white flash and camera shake for everyone nearby, a HUGE crater (CRATER_RADIUS, a
//     ragged bowl with fire and blackstone on the floor), and a mushroom cloud.
//   * Mobs within KILL_RADIUS die. Players are NOT hurt: everyone within FLING_RADIUS is flung
//     away from the blast and gets full Resistance, Fire Resistance and Slow Falling for a while.
//     Tamed pets (Big Cats, dogs, cats...) and named mobs are treated like players: flung, not killed.
// Bedrock is never removed. The crater is carved a few rows at a time (system.runJob), so the
// game doesn't freeze.

import { world, system, BlockVolume, EquipmentSlot, GameMode } from "@minecraft/server";

const BOMB_ID = "mymod:atomic_bomb";
const OWNER_PREFIX = "bigcat_bomb_"; // world dynamic property per placed bomb (for the redstone check)

const FUSE_SECONDS = 10;
const CHAIN_FUSE_SECONDS = 2; // when another explosion sets it off
const WARN_RADIUS = 240;
const CRATER_RADIUS = 55; // blocks: about 110 across (2.5x the first version; 5x was too much for an iPad)
const CRATER_RAISE = 12; // sphere centre this far above the bomb, so the crater is a bowl
const KILL_RADIUS = 90;
const FLING_RADIUS = 160;
const FLASH_RADIUS = 400;
const FLING_SPEED = 5; // blocks per tick at the centre, less further out
const PROTECT_TICKS = 400; // 20 s of Resistance V + Fire Resistance
const FLOOR_SCORCH = 0.3; // chance a crater floor block becomes blackstone
const FLOOR_FIRE = 0.12; // chance of fire on top
const CLOUD_TICKS = 140;
const REDSTONE_INTERVAL = 10;
const KEEP = ["minecraft:bedrock", "minecraft:barrier", "minecraft:end_portal_frame"];

// Never killed or flung: helper entities that belong to other features.
const IMMUNE = new Set(["mymod:laser_dot", "mymod:grapple_hook", "mymod:drowned_lure"]);

/** bomb key -> { dim, pos, explodeAt } while counting down */
const lit = new Map();

function safe(fn) {
  try {
    return fn();
  } catch {
    return undefined;
  }
}

const keyOf = (dimId, p) => `${dimId.replace("minecraft:", "")}_${p.x}_${p.y}_${p.z}`;
function parseKey(key) {
  const m = /^(.+)_(-?\d+)_(-?\d+)_(-?\d+)$/.exec(key);
  return m && { dimId: `minecraft:${m[1]}`, pos: { x: Number(m[2]), y: Number(m[3]), z: Number(m[4]) } };
}
const centerOf = (p) => ({ x: p.x + 0.5, y: p.y + 0.5, z: p.z + 0.5 });
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);

function playersNear(dim, at, radius) {
  return safe(() => dim.getPlayers({ location: at, maxDistance: radius })) ?? [];
}

// --------------------------------------------------------------------------- lighting

function light(dim, pos, seconds = FUSE_SECONDS) {
  const key = keyOf(dim.id, pos);
  if (lit.has(key)) return;
  lit.set(key, { dim, pos, explodeAt: system.currentTick + seconds * 20 });
  safe(() => dim.playSound("random.fuse", centerOf(pos), { volume: 2 }));
}

// Flint and steel / fire charge on the bomb. The before-event, so the flint and steel doesn't
// also set fire on top of it.
world.beforeEvents.playerInteractWithBlock.subscribe((ev) => {
  if (!ev.isFirstEvent || ev.block.typeId !== BOMB_ID) return;
  const item = ev.itemStack?.typeId;
  if (item !== "minecraft:flint_and_steel" && item !== "minecraft:fire_charge") return;
  ev.cancel = true;
  const { block, player } = ev;
  const dim = block.dimension;
  const pos = block.location;
  system.run(() => {
    light(dim, pos);
    if (item === "minecraft:fire_charge") useFireCharge(player);
  });
});

function useFireCharge(player) {
  if (safe(() => player.getGameMode()) === GameMode.Creative) return;
  const eq = player.getComponent("minecraft:equippable");
  const held = safe(() => eq.getEquipment(EquipmentSlot.Mainhand));
  if (held?.typeId !== "minecraft:fire_charge") return;
  if (held.amount > 1) {
    held.amount -= 1;
    safe(() => eq.setEquipment(EquipmentSlot.Mainhand, held));
  } else {
    safe(() => eq.setEquipment(EquipmentSlot.Mainhand, undefined));
  }
}

// Another explosion (TNT, a creeper, another atomic bomb) sets it off with a short fuse.
// The block is already gone, so put it back to count down.
world.afterEvents.blockExplode.subscribe((ev) => {
  if (ev.explodedBlockPermutation?.type?.id !== BOMB_ID) return;
  const { dimension: dim } = ev;
  const pos = ev.block.location;
  system.run(() => {
    safe(() => dim.setBlockType(pos, BOMB_ID));
    light(dim, pos, CHAIN_FUSE_SECONDS);
  });
});

// Remember placed bombs so the redstone check knows where to look.
world.afterEvents.playerPlaceBlock.subscribe((ev) => {
  if (ev.block.typeId === BOMB_ID) world.setDynamicProperty(OWNER_PREFIX + keyOf(ev.dimension.id, ev.block.location), true);
});

system.runInterval(() => {
  for (const id of world.getDynamicPropertyIds()) {
    if (!id.startsWith(OWNER_PREFIX)) continue;
    const key = id.slice(OWNER_PREFIX.length);
    if (lit.has(key)) continue;
    const b = parseKey(key);
    const dim = b && safe(() => world.getDimension(b.dimId));
    const block = dim && safe(() => dim.getBlock(b.pos));
    if (!block) continue; // chunk not loaded
    if (block.typeId !== BOMB_ID) {
      world.setDynamicProperty(id, undefined);
      continue;
    }
    if ((safe(() => block.getRedstonePower()) ?? 0) > 0) light(dim, b.pos);
  }
}, REDSTONE_INTERVAL);

// --------------------------------------------------------------------------- countdown

system.runInterval(() => {
  const now = system.currentTick;
  for (const [key, bomb] of [...lit]) {
    const { dim, pos } = bomb;
    const at = centerOf(pos);
    const block = safe(() => dim.getBlock(pos));
    if (block && block.typeId !== BOMB_ID) {
      lit.delete(key); // broken during the countdown: defused
      for (const p of playersNear(dim, at, WARN_RADIUS)) safe(() => p.onScreenDisplay.setActionBar("§aAtomic Bomb defused!"));
      continue;
    }
    const left = bomb.explodeAt - now;
    if (left <= 0) {
      lit.delete(key);
      world.setDynamicProperty(OWNER_PREFIX + key, undefined);
      detonate(dim, pos);
      continue;
    }
    const seconds = Math.ceil(left / 20);
    const beepEvery = seconds > 5 ? 20 : seconds > 2 ? 10 : 4;
    if (left % beepEvery === 0) {
      safe(() => dim.playSound("note.pling", at, { volume: 3, pitch: 0.6 + (FUSE_SECONDS - seconds) * 0.12 }));
    }
    if (left % 4 === 0) safe(() => dim.spawnParticle("minecraft:campfire_tall_smoke_particle", { ...at, y: at.y + 0.6 }));
    if (left % 20 === 0) {
      for (const p of playersNear(dim, at, WARN_RADIUS)) {
        safe(() => p.onScreenDisplay.setActionBar(`§c§l!! ATOMIC BOMB in ${seconds}... §r§7(break it to defuse)`));
      }
    }
  }
}, 1);

// --------------------------------------------------------------------------- boom

function isPet(e) {
  return !!(safe(() => e.getComponent("minecraft:tameable")?.isTamed) || e.nameTag);
}

function protect(e) {
  safe(() => e.addEffect("resistance", PROTECT_TICKS, { amplifier: 4, showParticles: false }));
  safe(() => e.addEffect("fire_resistance", PROTECT_TICKS, { showParticles: false }));
  system.runTimeout(() => {
    if (e.isValid) safe(() => e.addEffect("slow_falling", PROTECT_TICKS, { showParticles: false }));
  }, 6);
}

function fling(e, center, d) {
  const away = { x: e.location.x - center.x, z: e.location.z - center.z };
  const flat = Math.hypot(away.x, away.z) || 1;
  const speed = FLING_SPEED * (1 - d / FLING_RADIUS) + 0.8;
  const v = { x: (away.x / flat) * speed, y: 1.2 + speed * 0.3, z: (away.z / flat) * speed };
  if (e.typeId === "minecraft:player") return safe(() => e.applyKnockback({ x: v.x, z: v.z }, v.y));
  safe(() => (e.clearVelocity(), e.applyImpulse(v), true)) ?? safe(() => e.applyKnockback({ x: v.x, z: v.z }, v.y));
}

function detonate(dim, pos) {
  const center = centerOf(pos);
  safe(() => dim.setBlockType(pos, "minecraft:air"));

  // flash, shake and sound for everyone in range
  for (const p of playersNear(dim, center, FLASH_RADIUS)) {
    const d = dist(p.location, center);
    safe(() => p.runCommand("camera @s fade time 0.05 0.4 2.5 color 255 255 240"));
    safe(() => p.runCommand(`camerashake add @s ${d < FLING_RADIUS ? 2 : 0.8} 3 positional`));
    safe(() => p.playSound("random.explode", { volume: 4, pitch: 0.5 }));
    safe(() => p.playSound("ambient.weather.thunder", { volume: 4, pitch: 0.6 }));
    safe(() => p.playSound("mob.warden.sonic_boom", { volume: 4, pitch: 0.5 }));
  }

  // creatures: players and pets are flung and protected, everything else in range dies
  for (const e of safe(() => dim.getEntities({ location: center, maxDistance: FLING_RADIUS })) ?? []) {
    if (!e.isValid || IMMUNE.has(e.typeId) || e.typeId.startsWith("mymod:morph_")) continue;
    const d = dist(e.location, center);
    if (e.typeId === "minecraft:player") {
      if (safe(() => e.getGameMode()) === GameMode.Spectator) continue; // e.g. inside a Player Trap Orb
      protect(e);
      fling(e, center, d);
    } else if (!e.getComponent("minecraft:health")) {
      if (d < CRATER_RADIUS) safe(() => e.remove()); // dropped items, arrows... vaporised
    } else if (isPet(e) || safe(() => e.matches({ families: ["inanimate"] }))) {
      protect(e);
      fling(e, center, d);
    } else if (d < KILL_RADIUS) {
      safe(() => e.kill());
    } else {
      fling(e, center, d);
    }
  }

  for (let i = 0; i < 6; i++) {
    const r = 3 + i * 3;
    const a = Math.random() * Math.PI * 2;
    safe(() => dim.spawnParticle("minecraft:huge_explosion_emitter", { x: center.x + Math.cos(a) * r, y: center.y + 1, z: center.z + Math.sin(a) * r }));
  }
  mushroomCloud(dim, center);
  system.runJob(carve(dim, pos));
}

/** Remove a ragged sphere of blocks a row at a time, then scorch the floor. */
function* carve(dim, pos) {
  // Players get flung far away while this runs, so keep the crater's chunks loaded until it's
  // done (a circle ticking area of 4 chunks = 64 blocks covers CRATER_RADIUS). Without it the
  // far side of the crater can be cut off flat.
  const area = `bigcat_bomb_${pos.x}_${pos.y}_${pos.z}`.replace(/-/g, "m");
  safe(() => dim.runCommand(`tickingarea add circle ${pos.x} ${pos.y} ${pos.z} 4 ${area}`));
  try {
    yield* carveBlocks(dim, pos);
  } finally {
    safe(() => dim.runCommand(`tickingarea remove ${area}`));
  }
}

function* carveBlocks(dim, pos) {
  const R = CRATER_RADIUS;
  const cy = pos.y + CRATER_RAISE;
  const range = safe(() => dim.heightRange) ?? { min: -64, max: 320 };
  const options = { blockFilter: { excludeTypes: KEEP }, ignoreChunkBoundErrors: true };
  for (let dy = R; dy >= -R; dy--) {
    const y = cy + dy;
    if (y < range.min || y >= range.max) continue;
    for (let dz = -R; dz <= R; dz++) {
      const rr = R * R - dy * dy - dz * dz;
      if (rr <= 0) continue;
      const w = Math.floor(Math.sqrt(rr) + (Math.random() - 0.5) * 2.5);
      if (w < 0) continue;
      const from = { x: pos.x - w, y, z: pos.z + dz };
      const to = { x: pos.x + w, y, z: pos.z + dz };
      safe(() => dim.fillBlocks(new BlockVolume(from, to), "minecraft:air", options));
      yield;
    }
  }
  // scorch the crater floor
  for (let dz = -R; dz <= R; dz++) {
    for (let dx = -R; dx <= R; dx++) {
      if (dx * dx + dz * dz > R * R * 0.8) continue;
      const roll = Math.random();
      if (roll > FLOOR_SCORCH + FLOOR_FIRE) continue;
      const top = safe(() => dim.getTopmostBlock({ x: pos.x + dx, z: pos.z + dz }, range.min));
      if (!top || top.y > cy || top.typeId === "minecraft:bedrock" || top.isLiquid) continue;
      if (roll < FLOOR_SCORCH) safe(() => top.setType("minecraft:blackstone"));
      else safe(() => top.above()?.isAir && top.above().setType("minecraft:fire"));
      if (dx % 4 === 0) yield;
    }
  }
}

function mushroomCloud(dim, center) {
  let t = 0;
  const id = system.runInterval(() => {
    t += 4;
    if (t > CLOUD_TICKS) return system.clearRun(id);
    const rise = Math.min(1, t / 60); // the cloud climbs for 3 s, then hangs there
    const top = center.y + 6 + 30 * rise;
    for (let y = center.y + 2; y < top; y += 3) {
      const j = () => (Math.random() - 0.5) * 3;
      safe(() => dim.spawnParticle("minecraft:large_explosion", { x: center.x + j(), y, z: center.z + j() }));
    }
    const capR = 6 + 8 * rise;
    for (let i = 0; i < 10; i++) {
      const a = Math.random() * Math.PI * 2;
      const r = Math.random() * capR;
      const at = { x: center.x + Math.cos(a) * r, y: top + (Math.random() - 0.3) * 5, z: center.z + Math.sin(a) * r };
      safe(() => dim.spawnParticle(i % 3 ? "minecraft:large_explosion" : "minecraft:huge_explosion_emitter", at));
    }
  }, 4);
}
