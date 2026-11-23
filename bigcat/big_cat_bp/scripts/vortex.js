// Vortex Guns. Hand-written (not generated) - edit freely.
//
// Two guns, same vortex, different targets:
//   mymod:vortex_gun         "Monster Vortex": only hostile mobs (the "monster" family: zombies,
//                            skeletons, creepers, spiders, slimes, phantoms...). Tamed monsters are pets: skipped.
//   mymod:animal_vortex_gun  "Animal Vortex": everything else that's alive (animals, villagers,
//                            pets, tamed monsters...).
// Players are never pulled.
//
// Use (right-click / tap) one: for PULL_TICKS (5 s) every matching creature within RANGE blocks
// (256) is sucked towards you, faster the further away it is. Each creature gets its own spot on a
// spiral around you (so they don't pile up and crush each other) and is let go once it's there.
// Use it again (or sneak + use) to let go early.
// A creature can only be pulled if its chunk is loaded: in practice that's your simulation
// distance (Settings > Simulation Distance), not the full 256.
//
// Mobs are moved with clearVelocity + applyImpulse every PUSH_EVERY ticks, which sets their velocity.
// The portal particles need a "variable.direction" (where they drift to); without it the game
// logs errors for every particle, every frame, which is what made the first version lag.

import { world, system, MolangVariableMap } from "@minecraft/server";

/** gun item -> which creatures it pulls */
const GUNS = { "mymod:vortex_gun": "monsters", "mymod:animal_vortex_gun": "animals" };
const LABELS = { monsters: "monsters", animals: "animals" };

const RANGE = 256; // blocks
const PULL_TICKS = 100; // 5 s
const RESCAN_TICKS = 40; // look for creatures again (new ones that came into range)
const PUSH_EVERY = 2; // ticks between velocity updates (they keep flying in between)
const ARRIVE = 1.5; // blocks from its spot: let go
const SPOT_START = 3; // spiral of spots around you: first spot this far out...
const SPOT_SPREAD = 0.6; // ...and each further spot a little further (grows with sqrt of the count)
const MIN_SPEED = 0.6; // blocks per tick, close up
const MAX_SPEED = 4.0; // blocks per tick, far away
const SPEED_PER_BLOCK = 0.04; // speed grows with distance
const LIFT = 0.12; // a little upward pull so they hop over walls and fences
const MAX_CREATURES = 100; // per shot, nearest first (a big farm could have hundreds)
const TRAILS = 30; // only this many creatures get a particle trail
const COOLDOWN_TICKS = 20;
const SWIRL_POINTS = 6;
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5)); // spreads spiral spots evenly

// Never pulled: helper entities that belong to other features, and bosses that would wreck things.
const IMMUNE = new Set([
  "minecraft:player",
  "minecraft:ender_dragon",
  "mymod:laser_dot",
  "mymod:grapple_hook",
  "mymod:drowned_lure",
]);

/** playerId -> { player, until, creatures: Map<id, {entity, slot}>, slots, arrived, nextScan } */
const pulls = new Map();
/** playerId -> tick of last accepted use */
const lastUse = new Map();

function safe(fn) {
  try {
    return fn();
  } catch {
    return undefined;
  }
}

function isCreature(e, mode) {
  if (!e?.isValid || IMMUNE.has(e.typeId) || e.typeId.startsWith("mymod:morph_")) return false;
  if (!e.getComponent("minecraft:health")) return false; // items, arrows, XP orbs...
  if (safe(() => e.matches({ families: ["inanimate"] }))) return false; // armor stands, the drowned trap...
  const hostile = !!safe(() => e.matches({ families: ["monster"] })) && !safe(() => e.getComponent("minecraft:tameable")?.isTamed);
  return mode === "monsters" ? hostile : !hostile;
}

function particle(dim, id, at, direction) {
  const vars = new MolangVariableMap();
  vars.setVector3("variable.direction", direction);
  safe(() => dim.spawnParticle(id, at, vars));
}

function scan(pull) {
  const p = pull.player;
  const found =
    safe(() => p.dimension.getEntities({ location: p.location, maxDistance: RANGE, excludeTypes: ["minecraft:player"], closest: MAX_CREATURES * 2 })) ?? [];
  for (const e of found) {
    if (pull.slots >= MAX_CREATURES) break;
    if (pull.creatures.has(e.id) || pull.done.has(e.id) || !isCreature(e, pull.mode)) continue;
    pull.creatures.set(e.id, { entity: e, slot: pull.slots++ });
  }
  pull.nextScan = system.currentTick + RESCAN_TICKS;
}

/** Where creature number `slot` should end up, around the player. */
function spot(p, slot) {
  const r = SPOT_START + SPOT_SPREAD * Math.sqrt(slot) * 2;
  const a = slot * GOLDEN_ANGLE;
  return { x: p.location.x + Math.cos(a) * r, y: p.location.y + 0.5, z: p.location.z + Math.sin(a) * r };
}

function start(player, mode) {
  const now = system.currentTick;
  if (now - (lastUse.get(player.id) ?? -1000) < COOLDOWN_TICKS) return;
  lastUse.set(player.id, now);
  if (pulls.has(player.id) || player.isSneaking) {
    stop(player.id, "§7Vortex off.");
    return;
  }
  const pull = { player, mode, until: now + PULL_TICKS, creatures: new Map(), done: new Set(), slots: 0, nextScan: 0 };
  scan(pull);
  pulls.set(player.id, pull);
  safe(() => player.dimension.playSound("mob.warden.sonic_charge", player.location, { volume: 2, pitch: 0.6 }));
  safe(() => player.dimension.playSound("portal.trigger", player.location, { volume: 1, pitch: 1.5 }));
  safe(() => player.onScreenDisplay.setActionBar(`§5Vortex! §fPulling ${pull.creatures.size} ${LABELS[mode]}...`));
}

function stop(playerId, message) {
  const pull = pulls.get(playerId);
  pulls.delete(playerId);
  if (!pull) return;
  for (const { entity } of pull.creatures.values()) if (entity.isValid) safe(() => entity.clearVelocity());
  if (message && pull.player.isValid) safe(() => pull.player.onScreenDisplay.setActionBar(message));
}

system.runInterval(() => {
  const now = system.currentTick;
  for (const [playerId, pull] of [...pulls]) {
    const p = pull.player;
    if (!p.isValid || now >= pull.until) {
      stop(playerId, `§5Vortex done: §f${pull.slots} ${LABELS[pull.mode]} pulled.`);
      continue;
    }
    if (now >= pull.nextScan) scan(pull);
    const dim = p.dimension;
    const push = now % PUSH_EVERY === 0;

    for (const [id, c] of pull.creatures) {
      const e = c.entity;
      if (!e.isValid || e.dimension.id !== dim.id) {
        pull.creatures.delete(id);
        continue;
      }
      if (!push) continue;
      const target = spot(p, c.slot);
      const l = e.location;
      const d = { x: target.x - l.x, y: target.y - l.y, z: target.z - l.z };
      const dist = Math.hypot(d.x, d.y, d.z);
      if (dist < ARRIVE) {
        safe(() => e.clearVelocity());
        pull.creatures.delete(id); // there: stop moving it
        pull.done.add(id);
        continue;
      }
      const speed = Math.min(MAX_SPEED, MIN_SPEED + dist * SPEED_PER_BLOCK, dist);
      const v = { x: (d.x / dist) * speed, y: (d.y / dist) * speed + LIFT, z: (d.z / dist) * speed };
      safe(() => (e.clearVelocity(), e.applyImpulse(v), true)) ?? safe(() => e.applyKnockback({ x: v.x, z: v.z }, v.y));
      if (c.slot < TRAILS && now % 6 === 0) {
        particle(dim, "minecraft:portal_reverse_particle", l, { x: d.x / dist, y: d.y / dist, z: d.z / dist });
      }
    }

    // swirl around the player, drifting in towards them
    const t = now * 0.35;
    for (let i = 0; i < SWIRL_POINTS; i++) {
      const a = t + (i * Math.PI * 2) / SWIRL_POINTS;
      const r = 1.2 + (i % 2) * 0.6;
      const off = { x: Math.cos(a) * r, y: 0.2 + (i % 3) * 0.6, z: Math.sin(a) * r };
      const at = { x: p.location.x + off.x, y: p.location.y + off.y, z: p.location.z + off.z };
      particle(dim, "minecraft:portal_directional", at, { x: -off.x, y: 1 - off.y, z: -off.z });
    }
    if (now % 20 === 0) safe(() => dim.playSound("mob.enderdragon.flap", p.location, { volume: 0.8, pitch: 0.6 }));
  }
}, 1);

world.afterEvents.itemUse.subscribe((ev) => {
  const mode = GUNS[ev.itemStack?.typeId];
  if (mode && ev.source?.typeId === "minecraft:player") start(ev.source, mode);
});

// Clicking a block within reach doesn't fire itemUse (see drowned_trap.js).
world.beforeEvents.playerInteractWithBlock.subscribe((ev) => {
  const mode = GUNS[ev.itemStack?.typeId];
  if (!ev.isFirstEvent || !mode) return;
  ev.cancel = true;
  const { player } = ev;
  system.run(() => start(player, mode));
});

world.afterEvents.playerLeave.subscribe((ev) => {
  stop(ev.playerId);
  lastUse.delete(ev.playerId);
});
