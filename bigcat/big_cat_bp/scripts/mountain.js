// Mountain Seed. Hand-written (not generated) - edit freely.
//
// Use the mymod:mountain_seed on the ground (or aim at a block up to PLANT_RANGE away). After a
// few seconds of rumbling, a mountain rises out of that spot, one layer at a time, like lava
// welling up, until it's done. Every mountain is different.
//
// The shape is a FRACTAL: the diamond-square algorithm (Fournier, Fussell & Carpenter, 1982).
// Start with a 65x65 grid; set the corners; then repeat, at half the step size each time:
//   * diamond step: the middle of each square = average of its 4 corners + a random nudge,
//   * square step:  the middle of each edge    = average of its 4 neighbours + a random nudge,
// and the nudges shrink by ROUGHNESS each round. Big lumps at big scales, smaller lumps at
// smaller scales, the same pattern at every zoom level: that's what makes it a fractal (a
// "fractional Brownian surface"). We run it twice: one surface for the height, one to make
// the outline wiggly so the mountain isn't a perfect circle. A radial falloff makes the
// middle (where you planted it) the highest point.
//
// Blocks, by height and depth:
//   surface: grass with flowers low down, then moss and coarse dirt, then bare rock and
//            gravel, then snow and ice on the peaks; steep cliffs are always bare rock
//   just under the surface in the middle band: badlands-style stripes of terracotta
//   inside: stone, andesite, diorite, granite, tuff, deepslate at the bottom, with ores
//            (coal, copper, iron, redstone, lapis, gold, emerald, and rare diamonds)
// It only fills air, water, lava and plants: it never breaks a house or anything else.
// Creatures caught as it rises are lifted up on top of it.

import { world, system, GameMode } from "@minecraft/server";

const SEED_ID = "mymod:mountain_seed";

const PLANT_RANGE = 8;
const GRID_POWER = 6; // grid is 2^6 + 1 = 65 cells across
const PEAK = 48; // tallest possible height, blocks
const ROUGHNESS = 0.55; // 0.4 = smooth hills, 0.7 = jagged spikes
const EDGE_WOBBLE = 0.35; // how much the outline wiggles
const RUMBLE_TICKS = 60; // before it starts growing
const TICKS_PER_LAYER = 4; // growth speed
const COOLDOWN_TICKS = 10;
const SHAKE_RADIUS = 64;
const FOUNDATION_DEPTH = 12; // fill gaps under the mountain down to the ground, at most this deep

const REPLACEABLE = new Set([
  "minecraft:short_grass",
  "minecraft:tall_grass",
  "minecraft:fern",
  "minecraft:large_fern",
  "minecraft:snow_layer",
  "minecraft:deadbush",
  "minecraft:poppy",
  "minecraft:dandelion",
  "minecraft:vine",
  "minecraft:seagrass",
  "minecraft:kelp",
]);
const STONES = ["minecraft:stone", "minecraft:andesite", "minecraft:diorite", "minecraft:granite", "minecraft:tuff"];
const BANDS = [
  "minecraft:orange_terracotta",
  "minecraft:yellow_terracotta",
  "minecraft:white_terracotta",
  "minecraft:red_terracotta",
  "minecraft:brown_terracotta",
  "minecraft:light_gray_terracotta",
  "minecraft:orange_terracotta",
];
// [block, chance per interior block], checked in order
const ORES = [
  ["minecraft:diamond_ore", 0.002],
  ["minecraft:emerald_ore", 0.002],
  ["minecraft:gold_ore", 0.005],
  ["minecraft:lapis_ore", 0.005],
  ["minecraft:redstone_ore", 0.008],
  ["minecraft:iron_ore", 0.015],
  ["minecraft:copper_ore", 0.015],
  ["minecraft:coal_ore", 0.025],
];
const FLOWERS = ["minecraft:short_grass", "minecraft:short_grass", "minecraft:poppy", "minecraft:dandelion", "minecraft:cornflower", "minecraft:azure_bluet"];

/** playerId -> tick of last accepted use */
const lastUse = new Map();

function safe(fn) {
  try {
    return fn();
  } catch {
    return undefined;
  }
}

/** Small seeded random number generator (mulberry32), so one mountain = one seed. */
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Diamond-square: a (2^power + 1)^2 grid of fractal values, roughly in -1..1. */
function diamondSquare(power, roughness, rand) {
  const n = 2 ** power + 1;
  const g = Array.from({ length: n }, () => new Float32Array(n));
  const nudge = (amp) => (rand() * 2 - 1) * amp;
  for (const [x, z] of [[0, 0], [0, n - 1], [n - 1, 0], [n - 1, n - 1]]) g[x][z] = nudge(1);
  let amp = 1;
  for (let step = n - 1; step > 1; step /= 2) {
    const half = step / 2;
    // diamond step: centre of every square
    for (let x = half; x < n; x += step) {
      for (let z = half; z < n; z += step) {
        const avg = (g[x - half][z - half] + g[x - half][z + half] + g[x + half][z - half] + g[x + half][z + half]) / 4;
        g[x][z] = avg + nudge(amp);
      }
    }
    // square step: middle of every edge
    for (let x = 0; x < n; x += half) {
      for (let z = (x / half) % 2 === 0 ? half : 0; z < n; z += step) {
        let sum = 0;
        let cnt = 0;
        for (const [dx, dz] of [[-half, 0], [half, 0], [0, -half], [0, half]]) {
          const xx = x + dx;
          const zz = z + dz;
          if (xx >= 0 && xx < n && zz >= 0 && zz < n) {
            sum += g[xx][zz];
            cnt++;
          }
        }
        g[x][z] = sum / cnt + nudge(amp);
      }
    }
    amp *= roughness;
  }
  return g;
}

/** Heights (0 = nothing there) for a grid centred on the seed. */
function heightMap(seed) {
  const rand = rng(seed);
  const shape = diamondSquare(GRID_POWER, ROUGHNESS, rand);
  const edge = diamondSquare(GRID_POWER, 0.6, rand);
  const n = shape.length;
  const c = (n - 1) / 2;
  const h = Array.from({ length: n }, () => new Int16Array(n));
  for (let x = 0; x < n; x++) {
    for (let z = 0; z < n; z++) {
      const r = Math.hypot(x - c, z - c) / c / (1 + EDGE_WOBBLE * edge[x][z]); // 0 middle, 1 edge
      if (r >= 1) continue;
      const falloff = (1 - r) ** 1.7;
      const v = PEAK * falloff * (0.7 + 0.45 * shape[x][z]);
      h[x][z] = Math.max(0, Math.round(v));
    }
  }
  h[c][c] = Math.max(h[c][c], Math.round(PEAK * 0.7)); // the seed is always a peak
  return h;
}

// --------------------------------------------------------------------------- choosing blocks

function pick(list, rand) {
  return list[Math.floor(rand() * list.length)];
}

function slopeAt(h, x, z) {
  let s = 0;
  for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
    const v = h[x + dx]?.[z + dz] ?? 0;
    s = Math.max(s, Math.abs(h[x][z] - v));
  }
  return s;
}

function blockFor(y, top, slope, bandShift, rand, maxTop) {
  const frac = y / maxTop; // 0 at the bottom, 1 at this mountain's own peak
  const depth = top - y; // 0 = surface
  if (depth === 0) {
    if (frac > 0.78) return rand() < 0.8 ? "minecraft:snow" : "minecraft:packed_ice";
    if (slope >= 3) return pick(["minecraft:stone", "minecraft:andesite", "minecraft:tuff"], rand);
    if (frac > 0.6) return rand() < 0.7 ? "minecraft:stone" : "minecraft:gravel";
    if (frac > 0.4) return rand() < 0.5 ? "minecraft:calcite" : "minecraft:stone";
    if (frac > 0.25) return rand() < 0.6 ? "minecraft:moss_block" : "minecraft:coarse_dirt";
    return "minecraft:grass_block";
  }
  if (frac < 0.25 && depth <= 3 && slope < 3) return "minecraft:dirt";
  if (frac >= 0.25 && frac <= 0.65 && depth <= 5) return BANDS[(y + bandShift) % BANDS.length];
  const roll = rand();
  let acc = 0;
  for (const [ore, chance] of ORES) {
    acc += chance;
    if (roll < acc) return ore;
  }
  if (y < 6) return rand() < 0.7 ? "minecraft:deepslate" : "minecraft:tuff";
  return pick(STONES, rand);
}

// --------------------------------------------------------------------------- growing

function canFill(block) {
  return !!block && (block.isAir || block.isLiquid || REPLACEABLE.has(block.typeId));
}

function liftCreatures(dim, base, c, y) {
  const center = { x: base.x + 0.5, y: base.y + y, z: base.z + 0.5 };
  for (const e of safe(() => dim.getEntities({ location: center, maxDistance: c + 4 })) ?? []) {
    const at = safe(() => dim.getBlock({ x: Math.floor(e.location.x), y: Math.floor(e.location.y), z: Math.floor(e.location.z) }));
    if (at && !at.isAir && !at.isLiquid && !REPLACEABLE.has(at.typeId)) {
      safe(() => e.teleport({ x: e.location.x, y: Math.floor(e.location.y) + 1.05, z: e.location.z }));
    }
  }
}

// Only real problems are logged: console.warn shows up on screen as a Content Log warning.
const log = (msg) => console.warn(`[bigcat mountain] ${msg}`);

/** Set a block, logging the first failure of each grow (so problems show in the Content Log). */
function place(state, block, type) {
  try {
    block.setType(type);
  } catch (e) {
    if (!state.warned) log(`could not place ${type} at ${JSON.stringify(block.location)}: ${e}`);
    state.warned = true;
  }
}

/** Run a generator with system.runJob and call done() when it finishes. */
function runJobThen(gen, done) {
  system.runJob(
    (function* () {
      try {
        yield* gen;
      } catch (e) {
        log(`error while growing: ${e}`);
      }
      done();
    })()
  );
}

function* foundation(dim, base, h, c, rand, state) {
  // on uneven ground, fill the gaps under the mountain's edges so it doesn't float
  const n = h.length;
  for (let x = 0; x < n; x++) {
    for (let z = 0; z < n; z++) {
      if (h[x][z] <= 0) continue;
      for (let d = 1; d <= FOUNDATION_DEPTH; d++) {
        const block = safe(() => dim.getBlock({ x: base.x + x - c, y: base.y - d, z: base.z + z - c }));
        if (!canFill(block)) break;
        place(state, block, rand() < 0.7 ? "minecraft:stone" : "minecraft:dirt");
      }
    }
    yield;
  }
}

function* layer(dim, base, h, c, y, m, state) {
  const n = h.length;
  for (let x = 0; x < n; x++) {
    for (let z = 0; z < n; z++) {
      const top = h[x][z] - 1; // highest layer index in this column
      if (top < y) continue;
      const block = safe(() => dim.getBlock({ x: base.x + x - c, y: base.y + y, z: base.z + z - c }));
      if (!block) {
        state.unloaded++;
        continue;
      }
      if (!canFill(block)) continue;
      place(state, block, blockFor(y, top, slopeAt(h, x, z), m.bandShift, m.rand, m.maxTop));
      state.placed++;
      if (y === top && y / m.maxTop <= 0.25 && m.rand() < 0.15) {
        const above = safe(() => block.above());
        if (above?.isAir) place(state, above, pick(FLOWERS, m.rand));
      }
    }
    yield;
  }
}

function grow(dim, base, seed) {
  const h = heightMap(seed);
  const c = (h.length - 1) / 2;
  const rand = rng(seed ^ 0x9e3779b9);
  let maxTop = 0;
  for (const row of h) for (const v of row) maxTop = Math.max(maxTop, v);
  const m = { rand, maxTop, bandShift: Math.floor(rand() * BANDS.length) };
  const state = { placed: 0, unloaded: 0, warned: false };

  // rumble
  let t = 0;
  const rumble = system.runInterval(() => {
    safe(() => dim.playSound("dig.stone", base, { volume: 2, pitch: 0.4 }));
    safe(() => dim.spawnParticle("minecraft:huge_explosion_emitter", { ...base, y: base.y + 0.5 }));
    for (const p of safe(() => dim.getPlayers({ location: base, maxDistance: SHAKE_RADIUS })) ?? []) {
      safe(() => p.runCommand("camerashake add @s 0.3 0.6 positional"));
    }
    t += 10;
    if (t < RUMBLE_TICKS) return;
    system.clearRun(rumble);
    runJobThen(foundation(dim, base, h, c, rand, state), () => nextLayer(0));
  }, 10);

  // then one layer at a time from the ground up, TICKS_PER_LAYER apart
  function nextLayer(y) {
    if (y >= maxTop) return finish();
    runJobThen(layer(dim, base, h, c, y, m, state), () => {
      liftCreatures(dim, base, c, y);
      if (y % 3 === 0) safe(() => dim.playSound("dig.gravel", { ...base, y: base.y + y }, { volume: 3, pitch: 0.5 }));
      system.runTimeout(() => nextLayer(y + 1), TICKS_PER_LAYER);
    });
  }

  function finish() {
    safe(() => dim.playSound("random.levelup", { ...base, y: base.y + maxTop }, { volume: 3, pitch: 0.5 }));
    for (const p of safe(() => dim.getPlayers({ location: base, maxDistance: SHAKE_RADIUS * 2 })) ?? []) {
      safe(() => p.onScreenDisplay.setActionBar(`§aA mountain has grown! §7(${maxTop} blocks tall)`));
    }
  }
}

// --------------------------------------------------------------------------- planting

const OFFSETS = { Up: [0, 1, 0], Down: [0, -1, 0], North: [0, 0, -1], South: [0, 0, 1], East: [1, 0, 0], West: [-1, 0, 0] };

function useOneFromHand(player) {
  if (safe(() => player.getGameMode()) === GameMode.Creative) return true;
  const container = player.getComponent("minecraft:inventory")?.container;
  const slot = player.selectedSlotIndex;
  const item = container?.getItem(slot);
  if (item?.typeId !== SEED_ID) return false;
  if (item.amount > 1) {
    item.amount -= 1;
    container.setItem(slot, item);
  } else {
    container.setItem(slot, undefined);
  }
  return true;
}

function plant(player, clicked) {
  const now = system.currentTick;
  if (now - (lastUse.get(player.id) ?? -1000) < COOLDOWN_TICKS) return;
  lastUse.set(player.id, now);
  const hit = clicked ?? safe(() => player.getBlockFromViewDirection({ maxDistance: PLANT_RANGE }));
  if (!hit) {
    player.onScreenDisplay.setActionBar("§7Aim at the ground to plant the Mountain Seed.");
    return;
  }
  if (!useOneFromHand(player)) return;
  const [dx, dy, dz] = OFFSETS[hit.face] ?? OFFSETS.Up;
  const l = hit.block.location;
  const base = { x: l.x + dx, y: l.y + dy, z: l.z + dz };
  const dim = player.dimension;
  player.onScreenDisplay.setActionBar("§6The ground starts to rumble...");
  grow(dim, base, Math.floor(Math.random() * 2 ** 31));
}

world.afterEvents.itemUse.subscribe((ev) => {
  if (ev.itemStack?.typeId === SEED_ID && ev.source?.typeId === "minecraft:player") plant(ev.source);
});

// Clicking a block within reach doesn't fire itemUse (see drowned_trap.js).
world.beforeEvents.playerInteractWithBlock.subscribe((ev) => {
  if (!ev.isFirstEvent || ev.itemStack?.typeId !== SEED_ID) return;
  ev.cancel = true;
  const { player, block, blockFace } = ev;
  system.run(() => plant(player, { block, face: blockFace }));
});

world.afterEvents.playerLeave.subscribe((ev) => lastUse.delete(ev.playerId));
