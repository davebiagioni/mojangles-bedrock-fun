// Air Cannon. Hand-written (not generated) - edit freely.
//
// Use (right-click / tap) the mymod:air_cannon: a blast of air shoots out in a cone in front of
// you, up to RANGE blocks. Every player and creature in the cone (and dropped items, arrows...)
// is launched SUPER far in the direction you're looking, harder the closer it is.
//   * Look up: they go up. Look straight ahead: they fly far and a little up.
//   * Look straight down at the ground: the blast launches YOU into the air (a rocket jump).
// Launched players and Big Cats (and you, after a rocket jump) get Slow Falling a moment later,
// so a blast is never a fall-damage death. Other mobs land however they land.
//
// Players can't be moved with applyImpulse, so players get applyKnockback (sets their velocity);
// everything else gets clearVelocity + applyImpulse.

import { world, system, GameMode } from "@minecraft/server";

const CANNON_ID = "mymod:air_cannon";

const RANGE = 16; // blocks
const CONE_START = 1.2; // cone radius at the muzzle, blocks
const CONE_SPREAD = 0.35; // cone radius grows this much per block
const PUSH_NEAR = 6.0; // blocks per tick, right in front of you
const PUSH_FAR = 3.0; // blocks per tick, at the edge of RANGE
const MIN_LIFT = 0.7; // upward speed everyone gets, so they leave the ground and fly
const MAX_LIFT = 4.0;
const ROCKET_LOOK_DOWN = -0.75; // view direction y below this = rocket jump
const ROCKET_LIFT = 2.2;
const SAFE_FALL_DELAY = 8; // ticks before Slow Falling (so it doesn't cut the launch short)
const SAFE_FALL_TICKS = 160;
const COOLDOWN_TICKS = 10; // also de-duplicates itemUse + playerInteractWithBlock
const PROTECTED = new Set(["minecraft:player", "mymod:big_cat"]); // get Slow Falling after a launch

// Never pushed: helper entities that belong to other features.
const IMMUNE = new Set([
  "mymod:laser_dot",
  "mymod:grapple_hook",
  "mymod:drowned_lure",
]);

/** playerId -> tick of last accepted use */
const lastUse = new Map();

const add = (a, b) => ({ x: a.x + b.x, y: a.y + b.y, z: a.z + b.z });
const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });
const scale = (a, s) => ({ x: a.x * s, y: a.y * s, z: a.z * s });
const dot = (a, b) => a.x * b.x + a.y * b.y + a.z * b.z;
const len = (a) => Math.hypot(a.x, a.y, a.z);
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

function safe(fn) {
  try {
    return fn();
  } catch {
    return undefined;
  }
}

const middle = (e) => add(e.location, { x: 0, y: e.typeId === "minecraft:player" ? 0.9 : 0.4, z: 0 });

/** Set an entity's velocity to v (players need knockback, everything else takes an impulse). */
function launch(entity, v) {
  if (entity.typeId === "minecraft:player") {
    return safe(() => (entity.applyKnockback({ x: v.x, z: v.z }, v.y), true)) ?? false;
  }
  return (
    safe(() => (entity.clearVelocity(), entity.applyImpulse(v), true)) ??
    safe(() => (entity.applyKnockback({ x: v.x, z: v.z }, v.y), true)) ??
    false
  );
}

function safeLanding(entity) {
  if (!PROTECTED.has(entity.typeId)) return;
  system.runTimeout(() => {
    if (entity.isValid) safe(() => entity.addEffect("slow_falling", SAFE_FALL_TICKS, { showParticles: false }));
  }, SAFE_FALL_DELAY);
}

function canPush(entity, shooter) {
  if (!entity?.isValid || entity.id === shooter.id || IMMUNE.has(entity.typeId) || entity.typeId.startsWith("mymod:morph_")) return false;
  if (entity.typeId === "minecraft:player") {
    return safe(() => entity.getGameMode()) !== GameMode.Spectator; // e.g. inside a Player Trap Orb
  }
  return true;
}

function effects(dim, eye, dir) {
  safe(() => dim.playSound("wind_charge.burst", eye, { volume: 1.0, pitch: 0.7 }));
  safe(() => dim.spawnParticle("minecraft:wind_explosion_emitter", add(eye, scale(dir, 1.5))));
  for (let d = 2; d <= RANGE; d += 1.5) {
    const r = (CONE_START + d * CONE_SPREAD) * 0.6;
    for (let i = 0; i < 2; i++) {
      const jitter = { x: (Math.random() - 0.5) * r, y: (Math.random() - 0.5) * r, z: (Math.random() - 0.5) * r };
      safe(() => dim.spawnParticle("minecraft:white_smoke_particle", add(add(eye, scale(dir, d)), jitter)));
    }
  }
}

function blast(player) {
  const now = system.currentTick;
  if (now - (lastUse.get(player.id) ?? -1000) < COOLDOWN_TICKS) return;
  lastUse.set(player.id, now);

  const dim = player.dimension;
  const eye = player.getHeadLocation();
  const dir = player.getViewDirection();
  effects(dim, eye, dir);

  // Aiming at your feet: rocket jump.
  const ground = dir.y < ROCKET_LOOK_DOWN && safe(() => player.getBlockFromViewDirection({ maxDistance: 4 }));
  if (ground) {
    launch(player, { x: -dir.x * 0.6, y: ROCKET_LIFT, z: -dir.z * 0.6 });
    safeLanding(player);
  }

  const flat = Math.hypot(dir.x, dir.z) || 1;
  for (const e of safe(() => dim.getEntities({ location: eye, maxDistance: RANGE + 2 })) ?? []) {
    if (!canPush(e, player)) continue;
    const to = sub(middle(e), eye);
    const along = dot(to, dir);
    if (along < 0 || along > RANGE) continue;
    const off = len(sub(to, scale(dir, along)));
    if (off > CONE_START + along * CONE_SPREAD) continue;

    const speed = PUSH_NEAR + (PUSH_FAR - PUSH_NEAR) * (along / RANGE);
    // Horizontal part follows where you look; lift is never less than MIN_LIFT.
    const h = speed * flat;
    const v = {
      x: (dir.x / flat) * h,
      y: clamp(dir.y * speed + MIN_LIFT, MIN_LIFT, MAX_LIFT),
      z: (dir.z / flat) * h,
    };
    if (launch(e, v)) safeLanding(e);
  }
}

world.afterEvents.itemUse.subscribe((ev) => {
  if (ev.itemStack?.typeId === CANNON_ID && ev.source?.typeId === "minecraft:player") blast(ev.source);
});

// Clicking a block within reach doesn't fire itemUse, and the after-event only fires when the
// click did something, so use the before-event and blast on the next tick (like drowned_trap.js).
world.beforeEvents.playerInteractWithBlock.subscribe((ev) => {
  if (!ev.isFirstEvent || ev.itemStack?.typeId !== CANNON_ID) return;
  ev.cancel = true;
  const { player } = ev;
  system.run(() => blast(player));
});

world.afterEvents.playerLeave.subscribe((ev) => lastUse.delete(ev.playerId));
