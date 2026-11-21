// Grappling Gun. Hand-written (not generated) - edit freely.
//
// Use (right-click / tap) the mymod:grappling_gun: it fires a mymod:grapple_hook projectile.
//   * Hook hits a block:            you get reeled in to that spot.
//   * Hook hits a mob/player/thing: it gets reeled in to you.
//   * Hook flies further than MAX_RANGE or for longer than FLIGHT_TICKS: it's retracted.
// A rope of particles is drawn from you to the hook the whole time.
// The grapple lets go when you arrive, when the target arrives, after MAX_REEL_TICKS, when you
// get stuck, when you use the gun again, sneak, or switch away from the gun.
// While you are being reeled in (and for a moment after) you get Slow Falling, so letting go in
// mid-air or zipping down to a block never causes fall damage.
//
// Players can't be moved with applyImpulse, so players (you, or a hooked player) are moved with
// applyKnockback every tick, which sets their velocity. Other entities use clearVelocity +
// applyImpulse, which does the same.

import { world, system, EquipmentSlot } from "@minecraft/server";

const GUN_ID = "mymod:grappling_gun";
const HOOK_ID = "mymod:grapple_hook";
const ROPE_PARTICLE = "mymod:grapple_rope";

const HOOK_SPEED = 2.5; // blocks per tick
const MAX_RANGE = 40; // blocks; hook is retracted beyond this
const FLIGHT_TICKS = 30; // hook is retracted if it hasn't hit anything by then
const MAX_REEL_TICKS = 100; // 5 s
const SELF_SPEED = 1.1; // blocks per tick, you towards the hook
const TARGET_SPEED = 0.9; // blocks per tick, hooked entity towards you
const SELF_ARRIVE = 1.3; // blocks from the anchor point
const TARGET_ARRIVE = 2.2; // blocks from you
const STUCK_TICKS = 12; // let go if we stop getting closer for this long
const COOLDOWN_TICKS = 5; // also de-duplicates itemUse + playerInteractWithBlock
const ROPE_INTERVAL_TICKS = 2;
const ROPE_STEP = 0.45; // blocks between rope particles
const ROPE_MAX_POINTS = 100;
const SLOW_FALL_TICKS = 40;
const SWEEP_INTERVAL_TICKS = 20;
const DIMENSIONS = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"];

const NORMALS = {
  Up: { x: 0, y: 1, z: 0 },
  Down: { x: 0, y: -1, z: 0 },
  North: { x: 0, y: 0, z: -1 },
  South: { x: 0, y: 0, z: 1 },
  East: { x: 1, y: 0, z: 0 },
  West: { x: -1, y: 0, z: 0 },
};

/**
 * playerId -> {
 *   player, hook, dimensionId,
 *   phase: "flying" | "reel_self" | "reel_target",
 *   started, anchor (reel_self: where the hook stuck), goal (reel_self: where your middle should end up),
 *   target (reel_target), best, bestAt (closest distance so far, for stuck detection)
 * }
 */
const grapples = new Map();
/** playerId -> tick of last accepted use */
const lastUse = new Map();

// --- small vector helpers ---------------------------------------------------------------
const add = (a, b) => ({ x: a.x + b.x, y: a.y + b.y, z: a.z + b.z });
const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });
const scale = (a, s) => ({ x: a.x * s, y: a.y * s, z: a.z * s });
const len = (a) => Math.hypot(a.x, a.y, a.z);

const middle = (e) => add(e.location, { x: 0, y: e.typeId === "minecraft:player" ? 0.9 : 0.5, z: 0 });
const hand = (p) => add(p.location, { x: 0, y: 1.2, z: 0 });

function isHoldingGun(player) {
  try {
    return player.getComponent("minecraft:equippable")?.getEquipment(EquipmentSlot.Mainhand)?.typeId === GUN_ID;
  } catch {
    return false;
  }
}

function safe(fn) {
  try {
    return fn();
  } catch {
    return undefined;
  }
}

/** Set an entity's velocity to `v` (blocks per tick). Returns false if the entity can't be moved. */
function setVelocity(entity, v) {
  if (entity.typeId === "minecraft:player") {
    return safe(() => (entity.applyKnockback({ x: v.x, z: v.z }, v.y), true)) ?? false;
  }
  return (
    safe(() => (entity.clearVelocity(), entity.applyImpulse(v), true)) ??
    safe(() => (entity.applyKnockback({ x: v.x, z: v.z }, v.y), true)) ??
    false
  );
}

function slowFall(entity) {
  safe(() => entity.addEffect("slow_falling", SLOW_FALL_TICKS, { showParticles: false }));
}

// --- firing and letting go --------------------------------------------------------------
function fire(player) {
  const dir = player.getViewDirection();
  const start = add(player.getHeadLocation(), scale(dir, 1.0));
  let hook;
  try {
    hook = player.dimension.spawnEntity(HOOK_ID, start);
    const proj = hook.getComponent("minecraft:projectile");
    proj.owner = player;
    proj.shoot(scale(dir, HOOK_SPEED), { uncertainty: 0 });
  } catch {
    safe(() => hook?.remove());
    return;
  }
  grapples.set(player.id, {
    player,
    hook,
    dimensionId: player.dimension.id,
    phase: "flying",
    started: system.currentTick,
  });
  player.dimension.playSound("crossbow.shoot", player.location, { pitch: 1.3 });
}

function release(playerId, why) {
  const g = grapples.get(playerId);
  if (!g) return;
  grapples.delete(playerId);
  if (g.hook?.isValid) safe(() => g.hook.remove());
  const p = g.player;
  if (!p?.isValid) return;
  if (g.phase === "reel_target" && g.target?.isValid && g.target.typeId !== "minecraft:player") {
    safe(() => g.target.clearVelocity());
  }
  if (g.phase === "reel_self") slowFall(p);
  if (why === "missed") {
    p.dimension.playSound("random.click", p.location, { pitch: 0.6 });
  } else {
    p.dimension.playSound("random.click", p.location, { pitch: 1.4 });
  }
}

function onUse(player) {
  if (player?.typeId !== "minecraft:player") return;
  const now = system.currentTick;
  if (now - (lastUse.get(player.id) ?? -1000) < COOLDOWN_TICKS) return;
  lastUse.set(player.id, now);
  if (grapples.has(player.id)) {
    release(player.id, "let go");
  } else {
    fire(player);
  }
}

world.afterEvents.itemUse.subscribe((ev) => {
  if (ev.itemStack?.typeId === GUN_ID) onUse(ev.source);
});

// Using an item while looking at a block within reach can skip itemUse. Holding the button
// repeats this event; only the first one counts, or holding would fire/let go over and over.
world.afterEvents.playerInteractWithBlock.subscribe((ev) => {
  if (ev.isFirstEvent && ev.itemStack?.typeId === GUN_ID) onUse(ev.player);
});

// --- hook hits ----------------------------------------------------------------------------
function grappleForHook(hook) {
  if (hook?.typeId !== HOOK_ID) return undefined;
  for (const g of grapples.values()) if (g.hook?.id === hook.id) return g;
  return undefined;
}

world.afterEvents.projectileHitBlock.subscribe((ev) => {
  const g = grappleForHook(ev.projectile);
  if (!g || g.phase !== "flying") return;
  const face = safe(() => ev.getBlockHit().face);
  const n = NORMALS[face] ?? { x: 0, y: 0, z: 0 };
  // Aim your middle a little out from the face; on top of a block, aim high enough to land on it.
  const goal = add(ev.location, face === "Up" ? { x: 0, y: 1.0, z: 0 } : scale(n, 0.6));
  Object.assign(g, {
    phase: "reel_self",
    anchor: ev.location,
    goal,
    started: system.currentTick,
    best: Infinity,
    bestAt: system.currentTick,
  });
  g.player.dimension.playSound("random.anvil_land", ev.location, { volume: 0.4, pitch: 1.8 });
});

world.afterEvents.projectileHitEntity.subscribe((ev) => {
  const g = grappleForHook(ev.projectile);
  if (!g || g.phase !== "flying") return;
  const target = safe(() => ev.getEntityHit().entity);
  if (!target?.isValid || target.id === g.player.id || target.typeId === HOOK_ID) return;
  safe(() => g.hook.remove());
  Object.assign(g, {
    phase: "reel_target",
    hook: undefined,
    target,
    started: system.currentTick,
    best: Infinity,
    bestAt: system.currentTick,
  });
  g.player.dimension.playSound("random.anvil_land", target.location, { volume: 0.4, pitch: 1.8 });
  if (target.typeId === "minecraft:player") {
    target.onScreenDisplay.setActionBar(`${g.player.name} hooked you!`);
  }
});

// --- every tick: reel in --------------------------------------------------------------------
/** Track the closest distance so far; true if we haven't got any closer for STUCK_TICKS. */
function stuck(g, dist, now) {
  if (dist < g.best - 0.05) {
    g.best = dist;
    g.bestAt = now;
    return false;
  }
  return now - g.bestAt > STUCK_TICKS;
}

function tick(g, now) {
  const p = g.player;
  if (!p.isValid) return "gone";
  if (p.dimension.id !== g.dimensionId) return "gone";
  if (!isHoldingGun(p) || p.isSneaking) return "let go";

  if (g.phase === "flying") {
    if (!g.hook?.isValid) return "missed";
    if (now - g.started > FLIGHT_TICKS || len(sub(g.hook.location, p.location)) > MAX_RANGE) return "missed";
    return undefined;
  }

  if (now - g.started > MAX_REEL_TICKS) return "timeout";

  if (g.phase === "reel_self") {
    // Keep the hook exactly where it stuck, in case the projectile wobbles or falls.
    if (g.hook?.isValid && len(sub(g.hook.location, g.anchor)) > 0.5) safe(() => g.hook.teleport(g.anchor));
    const to = sub(g.goal, middle(p));
    const dist = len(to);
    if (dist < SELF_ARRIVE) {
      setVelocity(p, { x: 0, y: 0.35, z: 0 }); // little hop to help climb onto ledges
      return "arrived";
    }
    if (stuck(g, dist, now)) return "stuck";
    const speed = Math.min(SELF_SPEED, dist * 0.5);
    setVelocity(p, scale(to, speed / dist));
    if ((now - g.started) % 10 === 0) slowFall(p);
    return undefined;
  }

  // reel_target
  const t = g.target;
  if (!t?.isValid) return "gone";
  if (t.dimension.id !== g.dimensionId) return "gone";
  const to = sub(middle(p), middle(t));
  const dist = len(to);
  if (dist < TARGET_ARRIVE) return "arrived";
  if (dist > MAX_RANGE + 8) return "timeout";
  if (stuck(g, dist, now)) return "stuck";
  const speed = Math.min(TARGET_SPEED, dist * 0.4);
  if (!setVelocity(t, scale(to, speed / dist))) return "stuck";
  if (t.typeId === "minecraft:player") slowFall(t);
  return undefined;
}

function drawRope(g) {
  const p = g.player;
  const end =
    g.phase === "reel_target"
      ? safe(() => middle(g.target))
      : g.phase === "reel_self"
        ? g.anchor
        : safe(() => g.hook.location);
  if (!end) return;
  const from = hand(p);
  const d = sub(end, from);
  const dist = len(d);
  const n = Math.min(ROPE_MAX_POINTS, Math.floor(dist / ROPE_STEP));
  for (let i = 1; i <= n; i++) {
    const at = add(from, scale(d, i / (n + 1)));
    try {
      p.dimension.spawnParticle(ROPE_PARTICLE, at);
    } catch {
      return; // rope runs into unloaded chunks; skip the rest
    }
  }
}

system.runInterval(() => {
  const now = system.currentTick;
  for (const [id, g] of [...grapples]) {
    let why;
    try {
      why = tick(g, now);
    } catch {
      why = "gone";
    }
    if (why) {
      release(id, why);
    } else if (now % ROPE_INTERVAL_TICKS === 0) {
      safe(() => drawRope(g));
    }
  }
}, 1);

// Hooks never survive a reload: remove any hook this script session isn't tracking.
system.runInterval(() => {
  const live = new Set([...grapples.values()].map((g) => g.hook?.id).filter(Boolean));
  for (const dimId of DIMENSIONS) {
    const hooks = safe(() => world.getDimension(dimId).getEntities({ type: HOOK_ID })) ?? [];
    for (const h of hooks) if (!live.has(h.id)) safe(() => h.remove());
  }
}, SWEEP_INTERVAL_TICKS);

world.afterEvents.playerLeave.subscribe((ev) => {
  release(ev.playerId, "gone");
  lastUse.delete(ev.playerId);
});
