// Blasters. Hand-written (not generated) - edit freely.
//
// Five blasters, all "hold use to fire" (right-click / hold on touch):
//   mymod:laser_blaster  Laser Blaster: a thick, glowing beacon-style beam that burns through blocks
//                        and hurts and ignites creatures in it.
//   mymod:flame_blaster  Flame Blaster: an orange beam that doesn't break anything, but sets fire
//                        wherever it lands (and around it) and sets creatures in it alight for longer.
//   mymod:water_blaster  Water Blaster: a blue jet that puts out fire and cools lava.
//   mymod:ice_blaster    Ice Blaster: an icy beam that puts out fire, freezes water and lava, lays snow.
//   mymod:barf_blaster   Barf Blaster: a slimy green beam that makes whoever it hits throw up.
//
// The items have a long minecraft:use_modifiers use_duration, so the game tells us when the
// player starts and stops holding (itemStartUse / itemStopUse). A quick click (itemUse) gives a
// short burst. A beam fires every PULSE_TICKS while held.
//
// Laser Blaster, each pulse:
//   * burns through up to PIERCE blocks along the beam (no drops), up to RANGE blocks away.
//     That's at most PIERCE * 20 / PULSE_TICKS = 40 blocks a second per player, which the game
//     handles easily. Unbreakable blocks (bedrock, portals, command blocks...) and anything that
//     holds items (chests, furnaces, shulker boxes...) stop the beam instead, so nobody's stuff
//     gets deleted.
//   * draws a bright core (mymod:laser_beam) inside a wide soft glow (mymod:laser_glow), with
//     sparkles spiralling around it, like a beacon beam.
// Flame Blaster, each pulse:
//   * the beam stops at the first block. Fire is placed on the air block in front of the face it
//     hit, on top of the block if that's air, and a few random spots around (only on air with a
//     solid block underneath). Fire spreads by itself unless the doFireTick game rule is off.
//   * draws an orange beam (mymod:fire_beam) with flames along it.
// Water Blaster and Ice Blaster (the Flame Blaster's counters), each pulse:
//   * the beam stops at the first block (it goes into water and lava, so you can aim at them).
//     Within SPLASH_RADIUS of where it lands:
//       Water: puts out fire, turns lava into obsidian (still lava) or cobblestone (flowing lava).
//       Ice:   puts out fire, freezes still water into ice, lava into obsidian/cobblestone, and
//              lays snow on top of the ground.
//   * creatures in the beam are put out (no longer burning). Water pushes them back a little;
//     ice slows them down and gives them a small freezing hit.
// Barf Blaster, each pulse:
//   * the beam stops at the first block and doesn't change any blocks.
//   * creatures and players in the beam get sick: nausea (the screen wobbles, for players) and a
//     little hunger, and they throw up green chunks (mymod:barf_spew) out of their mouth with a
//     splat, every SPEW_TICKS, until SICK_TICKS after the last hit. It does no damage.
// Laser and Flame hurt and set fire to creatures and players in the beam. No blaster ever
// affects the shooter, their own tamed pets, or Morph Wand costumes.

import { world, system, EquipmentSlot, MolangVariableMap } from "@minecraft/server";

const BLASTER = "mymod:laser_blaster";
const FLAME_BLASTER = "mymod:flame_blaster";
const WATER_BLASTER = "mymod:water_blaster";
const ICE_BLASTER = "mymod:ice_blaster";
const BARF_BLASTER = "mymod:barf_blaster";
const BEAM_PARTICLE = "mymod:laser_beam";
const GLOW_PARTICLE = "mymod:laser_glow";
const FIRE_PARTICLE = "mymod:fire_beam";
const WATER_PARTICLE = "mymod:water_beam";
const ICE_PARTICLE = "mymod:ice_beam";
const BARF_PARTICLE = "mymod:barf_beam";
const SPEW_PARTICLE = "mymod:barf_spew";

/** item -> settings for that blaster */
const KINDS = {
  [BLASTER]: { kind: "laser", range: 64, damage: 8, fireSeconds: 3 },
  [FLAME_BLASTER]: { kind: "flame", range: 48, damage: 3, fireSeconds: 10 },
  [WATER_BLASTER]: { kind: "water", range: 40, push: 0.6 },
  [ICE_BLASTER]: { kind: "ice", range: 40, damage: 2, slowTicks: 60 },
  [BARF_BLASTER]: { kind: "barf", range: 32, nauseaTicks: 200 },
};

const PIERCE = 4; // blocks burnt per pulse (laser)
const PULSE_TICKS = 2;
const CLICK_TICKS = 6; // how long a single click keeps firing
const CORE_STEP = 0.7; // blocks between core particles
const GLOW_STEP = 1.2; // blocks between glow particles
const SPARKLE_STEP = 2.5; // blocks between spiral sparkles
const FIRE_STEP = 0.7; // blocks between flame-beam particles
const FIRE_SPREAD = 3; // random fire spots tried around where the flame beam lands, per pulse
const FIRE_RADIUS = 2;
const SPLASH_RADIUS = 3; // water / ice: blocks around where the beam lands
const SPRAY_STEP = 0.7;
const SICK_TICKS = 80; // barf: how long someone keeps throwing up after the last hit
const SPEW_TICKS = 3; // barf: ticks between spews
const HUM_PULSES = 5; // the humming sound repeats every this many pulses

const UNBREAKABLE = new Set([
  "minecraft:bedrock",
  "minecraft:barrier",
  "minecraft:command_block",
  "minecraft:chain_command_block",
  "minecraft:repeating_command_block",
  "minecraft:structure_block",
  "minecraft:structure_void",
  "minecraft:jigsaw",
  "minecraft:end_portal",
  "minecraft:end_portal_frame",
  "minecraft:end_gateway",
  "minecraft:portal",
  "minecraft:reinforced_deepslate",
  "minecraft:allow",
  "minecraft:deny",
  "minecraft:border_block",
  "minecraft:light_block",
]);
const NEVER_HIT = new Set(["mymod:laser_dot", "mymod:grapple_hook", "minecraft:item", "minecraft:xp_orb"]);
const OFFSETS = { Up: [0, 1, 0], Down: [0, -1, 0], North: [0, 0, -1], South: [0, 0, 1], East: [1, 0, 0], West: [-1, 0, 0] };

/** playerId -> { player, item, holding, until, pulses } */
const shooters = new Map();

function safe(fn) {
  try {
    return fn();
  } catch {
    return undefined;
  }
}

const add = (a, d, k) => ({ x: a.x + d.x * k, y: a.y + d.y * k, z: a.z + d.z * k });
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);

function heldItem(player) {
  return safe(() => player.getComponent("minecraft:equippable").getEquipment(EquipmentSlot.Mainhand))?.typeId;
}

/** World position of a block raycast hit (faceLocation is block-relative; see main.js). */
function hitPoint(hit) {
  const b = hit.block.location;
  const f = hit.faceLocation;
  const relative = Math.abs(f.x) <= 1.01 && Math.abs(f.y) <= 1.01 && Math.abs(f.z) <= 1.01;
  return relative ? { x: b.x + f.x, y: b.y + f.y, z: b.z + f.z } : { x: f.x, y: f.y, z: f.z };
}

function canBurn(block) {
  if (!block || block.isAir || block.isLiquid || UNBREAKABLE.has(block.typeId)) return false;
  return !safe(() => block.getComponent("minecraft:inventory")); // chests, furnaces, hoppers...
}

/** Where the beam is drawn from: just right of and below the eyes (where the gun is). */
function muzzle(eye, dir) {
  const right = { x: -dir.z, y: 0, z: dir.x };
  const rl = Math.hypot(right.x, right.z) || 1;
  return add(add(add(eye, dir, 0.6), { x: right.x / rl, y: 0, z: right.z / rl }, 0.3), { x: 0, y: -1, z: 0 }, 0.25);
}

/** Call affect(entity) for every creature in the beam the blaster is allowed to touch. */
function inBeam(player, length, affect) {
  // The ray stops at blocks (and the laser's burnt ones are air now).
  const hits = safe(() => player.getEntitiesFromViewDirection({ maxDistance: length })) ?? [];
  for (const { entity } of hits) {
    if (!entity?.isValid || entity.id === player.id || NEVER_HIT.has(entity.typeId) || entity.typeId.startsWith("mymod:morph_")) continue;
    if (safe(() => entity.getComponent("minecraft:tameable")?.tamedToPlayerId) === player.id) continue;
    affect(entity);
  }
}

function hurtCreatures(player, length, cfg) {
  inBeam(player, length, (entity) => {
    safe(() => entity.applyDamage(cfg.damage, { cause: "entityAttack", damagingEntity: player }));
    safe(() => entity.setOnFire(cfg.fireSeconds, true)); // also between hits: keep it burning
  });
}

// --------------------------------------------------------------------------- Laser Blaster

function fireLaser(player, pulse, cfg) {
  const dim = player.dimension;
  const eye = player.getHeadLocation();
  const dir = player.getViewDirection();

  // Blocks: burn through up to PIERCE, stop at the next one after that (or an unbreakable one).
  let end = add(eye, dir, cfg.range);
  let from = eye;
  let burnt = 0;
  for (let i = 0; i <= PIERCE; i++) {
    const left = cfg.range - dist(eye, from);
    if (left <= 0) break;
    const hit = safe(() =>
      dim.getBlockFromRay(from, dir, { maxDistance: left, includeLiquidBlocks: false, includePassableBlocks: true }),
    );
    if (!hit) break;
    const p = hitPoint(hit);
    if (burnt >= PIERCE || !canBurn(hit.block)) {
      end = p;
      break;
    }
    const loc = hit.block.location;
    let ok = true;
    try {
      dim.setBlockType(loc, "minecraft:air");
    } catch {
      ok = false; // e.g. the chunk isn't loaded
    }
    if (ok) {
      burnt++;
      const c = { x: loc.x + 0.5, y: loc.y + 0.5, z: loc.z + 0.5 };
      safe(() => dim.spawnParticle("minecraft:basic_flame_particle", c));
      if (burnt === 1) safe(() => dim.playSound("random.fizz", c, { volume: 0.4, pitch: 1.6 }));
    }
    from = p;
    end = p;
  }
  hurtCreatures(player, dist(eye, end), cfg);

  // The beacon beam: bright core, wide soft glow, and sparkles spiralling around it.
  const start = muzzle(eye, dir);
  const span = dist(start, end);
  const step = { x: (end.x - start.x) / span, y: (end.y - start.y) / span, z: (end.z - start.z) / span };
  for (let d = 0; d < span; d += CORE_STEP) safe(() => dim.spawnParticle(BEAM_PARTICLE, add(start, step, d)));
  for (let d = GLOW_STEP / 2; d < span; d += GLOW_STEP) safe(() => dim.spawnParticle(GLOW_PARTICLE, add(start, step, d)));
  // two unit vectors at right angles to the beam, for the spiral
  const up = Math.abs(step.y) > 0.9 ? { x: 1, y: 0, z: 0 } : { x: 0, y: 1, z: 0 };
  const u = { x: step.y * up.z - step.z * up.y, y: step.z * up.x - step.x * up.z, z: step.x * up.y - step.y * up.x };
  const ul = Math.hypot(u.x, u.y, u.z) || 1;
  u.x /= ul;
  u.y /= ul;
  u.z /= ul;
  const w = { x: step.y * u.z - step.z * u.y, y: step.z * u.x - step.x * u.z, z: step.x * u.y - step.y * u.x };
  for (let d = 1; d < span; d += SPARKLE_STEP) {
    const a = d * 1.3 + pulse * 0.8;
    const r = 0.35;
    const at = add(add(add(start, step, d), u, Math.cos(a) * r), w, Math.sin(a) * r);
    safe(() => dim.spawnParticle(BEAM_PARTICLE, at));
  }
  for (let i = 0; i < 2; i++) safe(() => dim.spawnParticle(GLOW_PARTICLE, end));

  if (pulse % HUM_PULSES === 0) safe(() => dim.playSound("beacon.ambient", eye, { volume: 0.8, pitch: 1.8 }));
}

// --------------------------------------------------------------------------- Flame Blaster

/** Put fire at `loc` if it's air with something solid under it. Returns true if it did. */
function ignite(dim, loc) {
  const block = safe(() => dim.getBlock(loc));
  if (!block?.isAir) return false;
  const below = safe(() => block.below());
  if (!below || below.isAir || below.isLiquid) return false;
  return safe(() => (block.setType("minecraft:fire"), true)) ?? false;
}

function fireFlame(player, pulse, cfg) {
  const dim = player.dimension;
  const eye = player.getHeadLocation();
  const dir = player.getViewDirection();

  const hit = safe(() => dim.getBlockFromRay(eye, dir, { maxDistance: cfg.range, includeLiquidBlocks: true, includePassableBlocks: false }));
  const end = hit ? hitPoint(hit) : add(eye, dir, cfg.range);
  hurtCreatures(player, dist(eye, end), cfg);

  if (hit && !hit.block.isLiquid) {
    const l = hit.block.location;
    const [dx, dy, dz] = OFFSETS[hit.face] ?? OFFSETS.Up;
    let lit = 0;
    // in front of the face that was hit (fire on a wall needs the block under it to be solid too;
    // a fire block next to a flammable wall also works, the game keeps it if it can burn)
    if (ignite(dim, { x: l.x + dx, y: l.y + dy, z: l.z + dz })) lit++;
    else if (safe(() => hit.block.above()?.isAir) && ignite(dim, { x: l.x, y: l.y + 1, z: l.z })) lit++;
    for (let i = 0; i < FIRE_SPREAD; i++) {
      const at = {
        x: l.x + Math.round((Math.random() * 2 - 1) * FIRE_RADIUS),
        y: l.y + Math.round(Math.random() * 2 - 0.5),
        z: l.z + Math.round((Math.random() * 2 - 1) * FIRE_RADIUS),
      };
      if (ignite(dim, at)) lit++;
    }
    if (lit && pulse % 3 === 0) safe(() => dim.playSound("fire.ignite", end, { volume: 0.8, pitch: 0.8 + Math.random() * 0.4 }));
  }

  // the beam: orange core with flames licking off it
  const start = muzzle(eye, dir);
  const span = dist(start, end);
  const step = { x: (end.x - start.x) / span, y: (end.y - start.y) / span, z: (end.z - start.z) / span };
  for (let d = 0; d < span; d += FIRE_STEP) safe(() => dim.spawnParticle(FIRE_PARTICLE, add(start, step, d)));
  for (let d = 1 + (pulse % 2); d < span; d += 3) safe(() => dim.spawnParticle("minecraft:basic_flame_particle", add(start, step, d)));
  for (let i = 0; i < 3; i++) safe(() => dim.spawnParticle("minecraft:basic_flame_particle", end));
  if (pulse % 4 === 0) safe(() => dim.spawnParticle("minecraft:lava_particle", end));

  if (pulse % HUM_PULSES === 0) safe(() => dim.playSound("mob.blaze.shoot", eye, { volume: 0.5, pitch: 0.7 }));
}

// --------------------------------------------------------------------------- Water and Ice Blasters

const FIRES = new Set(["minecraft:fire", "minecraft:soul_fire"]);
const LAVAS = new Set(["minecraft:lava", "minecraft:flowing_lava"]);
const WATERS = new Set(["minecraft:water", "minecraft:flowing_water"]);

const isSource = (block) => (safe(() => block.permutation.getState("liquid_depth")) ?? 0) === 0;

/** Put out fire and cool lava around `center`; Ice also freezes water and lays snow. Returns what happened. */
function soak(dim, center, freeze) {
  const r = SPLASH_RADIUS;
  const did = { fire: 0, lava: 0, ice: 0 };
  for (let dx = -r; dx <= r; dx++) {
    for (let dy = -r; dy <= r; dy++) {
      for (let dz = -r; dz <= r; dz++) {
        if (dx * dx + dy * dy + dz * dz > r * r) continue;
        const block = safe(() => dim.getBlock({ x: center.x + dx, y: center.y + dy, z: center.z + dz }));
        if (!block) continue;
        const t = block.typeId;
        if (FIRES.has(t)) {
          if (safe(() => (block.setType("minecraft:air"), true))) did.fire++;
        } else if (LAVAS.has(t)) {
          if (safe(() => (block.setType(isSource(block) ? "minecraft:obsidian" : "minecraft:cobblestone"), true))) did.lava++;
        } else if (freeze && WATERS.has(t) && isSource(block) && safe(() => block.above()?.isAir)) {
          if (safe(() => (block.setType("minecraft:ice"), true))) did.ice++; // only the surface, like real ice
        } else if (freeze && block.isAir && Math.random() < 0.35) {
          const below = safe(() => block.below());
          if (below && !below.isAir && !below.isLiquid && below.typeId !== "minecraft:snow_layer" && !FIRES.has(below.typeId)) {
            safe(() => block.setType("minecraft:snow_layer"));
          }
        }
      }
    }
  }
  return did;
}

function fireSpray(player, pulse, cfg) {
  const dim = player.dimension;
  const eye = player.getHeadLocation();
  const dir = player.getViewDirection();
  const freeze = cfg.kind === "ice";

  // stop at the first block, water and lava included; fire counts too, so you can aim at flames
  const hit = safe(() => dim.getBlockFromRay(eye, dir, { maxDistance: cfg.range, includeLiquidBlocks: true, includePassableBlocks: true }));
  const end = hit ? hitPoint(hit) : add(eye, dir, cfg.range);

  inBeam(player, dist(eye, end), (entity) => {
    safe(() => entity.extinguishFire(true));
    if (freeze) {
      safe(() => entity.addEffect("slowness", cfg.slowTicks, { amplifier: 3 }));
      safe(() => entity.applyDamage(cfg.damage, { cause: "freezing", damagingEntity: player }));
    } else {
      safe(() => entity.applyKnockback({ x: dir.x * cfg.push, z: dir.z * cfg.push }, 0.15));
    }
  });

  if (hit && pulse % 2 === 0) {
    const did = soak(dim, hit.block.location, freeze);
    if (did.fire || did.lava) safe(() => dim.playSound("random.fizz", end, { volume: 0.8, pitch: 1.0 }));
    if (did.lava) safe(() => dim.spawnParticle("minecraft:water_evaporation_manual", end));
    if (did.ice) safe(() => dim.playSound("random.glass", end, { volume: 0.5, pitch: 1.6 }));
  }

  const start = muzzle(eye, dir);
  const span = dist(start, end);
  const step = { x: (end.x - start.x) / span, y: (end.y - start.y) / span, z: (end.z - start.z) / span };
  for (let d = 0; d < span; d += SPRAY_STEP) safe(() => dim.spawnParticle(freeze ? ICE_PARTICLE : WATER_PARTICLE, add(start, step, d)));
  const extra = freeze ? "minecraft:snowflake_particle" : "minecraft:water_splash_particle_manual";
  for (let d = 1 + (pulse % 2); d < span; d += 3) safe(() => dim.spawnParticle(extra, add(start, step, d)));
  for (let i = 0; i < 4; i++) safe(() => dim.spawnParticle(extra, end));

  if (pulse % HUM_PULSES === 0) {
    safe(() => dim.playSound(freeze ? "random.glass" : "random.splash", eye, { volume: freeze ? 0.3 : 0.5, pitch: freeze ? 1.8 : 1.2 }));
  }
}

// --------------------------------------------------------------------------- Barf Blaster

/** entityId -> { entity, until } : who is throwing up, and until which tick */
const sick = new Map();

function fireBarf(player, pulse, cfg) {
  const dim = player.dimension;
  const eye = player.getHeadLocation();
  const dir = player.getViewDirection();
  const now = system.currentTick;

  const hit = safe(() => dim.getBlockFromRay(eye, dir, { maxDistance: cfg.range, includeLiquidBlocks: true, includePassableBlocks: false }));
  const end = hit ? hitPoint(hit) : add(eye, dir, cfg.range);

  inBeam(player, dist(eye, end), (entity) => {
    safe(() => entity.addEffect("nausea", cfg.nauseaTicks, { amplifier: 0, showParticles: false }));
    if (entity.typeId === "minecraft:player") safe(() => entity.addEffect("hunger", 100, { amplifier: 1, showParticles: false }));
    const rec = sick.get(entity.id);
    if (rec) rec.until = now + SICK_TICKS;
    else {
      sick.set(entity.id, { entity, until: now + SICK_TICKS });
      safe(() => dim.playSound("mob.llama.spit", entity.location, { volume: 1.0, pitch: 0.6 }));
    }
  });

  const start = muzzle(eye, dir);
  const span = dist(start, end);
  const step = { x: (end.x - start.x) / span, y: (end.y - start.y) / span, z: (end.z - start.z) / span };
  for (let d = 0; d < span; d += SPRAY_STEP) safe(() => dim.spawnParticle(BARF_PARTICLE, add(start, step, d)));
  for (let d = 1 + (pulse % 2); d < span; d += 3) safe(() => dim.spawnParticle("minecraft:villager_angry", add(start, step, d)));
  if (pulse % 2 === 0) safe(() => dim.spawnParticle("minecraft:sneeze", end));

  if (pulse % HUM_PULSES === 0) safe(() => dim.playSound("mob.slime.small", eye, { volume: 0.6, pitch: 0.8 }));
}

/** Throw up: chunks out of the mouth, in the direction the creature is looking (and a bit down). */
function spew(entity, n) {
  const dim = entity.dimension;
  const head = entity.getHeadLocation();
  const look = safe(() => entity.getViewDirection()) ?? { x: 0, y: 0, z: 1 };
  const flat = Math.hypot(look.x, look.z) || 1;
  // mostly forward, tipped downwards, like leaning over
  const dir = { x: look.x / flat, y: Math.min(look.y, 0) - 0.35, z: look.z / flat };
  const mouth = { x: head.x + dir.x * 0.35, y: head.y - 0.2, z: head.z + dir.z * 0.35 };
  const vars = new MolangVariableMap();
  vars.setVector3("variable.direction", dir);
  safe(() => dim.spawnParticle(SPEW_PARTICLE, mouth, vars));
  if (n % 4 === 0) safe(() => dim.playSound(Math.random() < 0.5 ? "mob.slime.big" : "mob.llama.spit", mouth, { volume: 0.8, pitch: 0.5 + Math.random() * 0.3 }));
}

system.runInterval(() => {
  const now = system.currentTick;
  for (const [id, rec] of sick) {
    const e = rec.entity;
    if (!e.isValid || now > rec.until) {
      if (e.isValid) safe(() => e.dimension.playSound("random.burp", e.location, { volume: 0.8, pitch: 0.8 }));
      sick.delete(id);
      continue;
    }
    spew(e, Math.floor(now / SPEW_TICKS));
  }
}, SPEW_TICKS);

// --------------------------------------------------------------------------- trigger

const START_SOUNDS = {
  laser: ["beacon.activate", 2.0],
  flame: ["mob.ghast.fireball", 1.0],
  water: ["bucket.empty_water", 1.0],
  ice: ["random.glass", 0.6],
  barf: ["mob.slime.big", 0.6],
};

function start(player, item, holding) {
  const now = system.currentTick;
  const rec = shooters.get(player.id) ?? { player, item, holding: false, until: 0, pulses: 0 };
  if (!shooters.has(player.id)) {
    const [sound, pitch] = START_SOUNDS[KINDS[item].kind];
    safe(() => player.dimension.playSound(sound, player.location, { pitch }));
  }
  rec.item = item;
  if (holding) rec.holding = true;
  rec.until = Math.max(rec.until, now + CLICK_TICKS);
  shooters.set(player.id, rec);
}

function stop(player) {
  const rec = shooters.get(player.id);
  if (rec) rec.holding = false;
}

world.afterEvents.itemStartUse.subscribe((ev) => {
  if (KINDS[ev.itemStack?.typeId]) start(ev.source, ev.itemStack.typeId, true);
});
world.afterEvents.itemUse.subscribe((ev) => {
  if (KINDS[ev.itemStack?.typeId]) start(ev.source, ev.itemStack.typeId, false);
});
world.afterEvents.itemStopUse.subscribe((ev) => {
  if (KINDS[ev.itemStack?.typeId] || ev.itemStack === undefined) stop(ev.source);
});
world.afterEvents.itemReleaseUse.subscribe((ev) => {
  if (KINDS[ev.itemStack?.typeId]) stop(ev.source);
});
world.afterEvents.playerLeave.subscribe((ev) => {
  shooters.delete(ev.playerId);
  sick.delete(ev.playerId);
});

system.runInterval(() => {
  const now = system.currentTick;
  for (const [id, rec] of shooters) {
    const p = rec.player;
    if (!p.isValid || heldItem(p) !== rec.item || (!rec.holding && now > rec.until)) {
      shooters.delete(id);
      continue;
    }
    const cfg = KINDS[rec.item];
    if (cfg.kind === "flame") fireFlame(p, rec.pulses++, cfg);
    else if (cfg.kind === "water" || cfg.kind === "ice") fireSpray(p, rec.pulses++, cfg);
    else if (cfg.kind === "barf") fireBarf(p, rec.pulses++, cfg);
    else fireLaser(p, rec.pulses++, cfg);
  }
}, PULSE_TICKS);
