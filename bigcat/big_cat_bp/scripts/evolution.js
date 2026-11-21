// Evolution Stone. Hand-written (not generated) - edit freely.
//
// * Mining any ore (coal, iron, copper, gold, redstone, lapis, diamond, emerald, nether gold,
//   nether quartz, and their deepslate versions) has a small chance to drop an Evolution Stone,
//   like redstone dust drops from redstone ore. Fortune raises the chance; Silk Touch and
//   Creative mode never drop one.
// * Use a stone on a tamed Big Cat to evolve it one stage (8 stages). Each stage is tougher,
//   stronger and faster (component groups made by tools/gen_evolution.py) and the cat gives off
//   its own subtle particles. Evolving heals the cat fully.
// * At stage 8 the cat grows wings. Ride it and jump to take off; in the air it flies where
//   you look while you hold forward, climbs while you hold jump and hovers when you let go.
//   Land by flying into the ground. If you get off mid-air you get Slow Falling.
//
// The stage is the int entity property mymod:evolution (0-8). STAGES below must match STAGES
// in tools/gen_evolution.py (validate.py checks the names and particles).

import { world, system, ItemStack, GameMode } from "@minecraft/server";

const STONE_ID = "mymod:evolution_stone";
const CAT_ID = "mymod:big_cat";
const PROP = "mymod:evolution";
const WING_STAGE = 8;

// name, colour code, ambient particle (vanilla particles that need no Molang variables)
const STAGES = [
  { name: "Sprout", color: "§a", particle: "minecraft:villager_happy" },
  { name: "Blossom", color: "§d", particle: "minecraft:cherry_leaves_particle" },
  { name: "Frost", color: "§b", particle: "minecraft:snowflake_particle" },
  { name: "Ember", color: "§6", particle: "minecraft:basic_flame_particle" },
  { name: "Soulfire", color: "§3", particle: "minecraft:blue_flame_particle" },
  { name: "Firefly", color: "§e", particle: "minecraft:firefly_particle" },
  { name: "Arcane", color: "§5", particle: "minecraft:obsidian_glow_dust_particle" },
  { name: "Celestial", color: "§f", particle: "minecraft:endrod" },
];
const MAX_STAGE = STAGES.length;

// --- ore drops
const DROP_CHANCE = 0.05; // per ore block; each Fortune level adds half of this again
const FORTUNE_BONUS = 0.5;

// --- evolving
const USE_RANGE = 8; // blocks, when using the stone in the air while aiming at a cat
const COOLDOWN_TICKS = 6; // one click can fire both a before-event and itemUse
const BURST_PARTICLES = 16;

// --- ambient particles
const AURA_INTERVAL_TICKS = 10; // one particle per evolved cat this often: subtle on purpose

// --- flight (velocities in blocks per tick)
const FLY_SPEED = 0.7; // holding forward: along the rider's view direction
const BACK_SPEED = 0.2; // holding back
const CLIMB_SPEED = 0.4; // holding jump
const TAKEOFF_SPEED = 0.6; // jump on the ground
const SINK_SPEED = 0.02; // no input: drift down very slowly
const STEERING = 0.3; // 0..1, how quickly the cat reaches the wanted velocity (lower = floatier)
const GRAVITY_LIFT = 0.08; // added every tick to cancel gravity; raise if the cat sinks while hovering
const DISMOUNT_SLOW_FALL_TICKS = 200;

const DIMENSIONS = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"];

function safe(fn) {
  try {
    return fn();
  } catch {
    return undefined;
  }
}

function tell(player, text) {
  player.onScreenDisplay.setActionBar(text);
}

function isCreative(player) {
  return safe(() => player.getGameMode() === GameMode.Creative) ?? false;
}

function stageOf(cat) {
  const s = safe(() => cat.getProperty(PROP));
  return typeof s === "number" ? s : 0;
}

function catName(cat) {
  return cat.nameTag || "Your Big Cat";
}

/** A random point in and around the cat's body, scaled with the cat (babies are smaller). */
function aroundCat(cat) {
  const scale = safe(() => cat.getComponent("minecraft:scale")?.value) ?? 1;
  const l = cat.location;
  const r = 0.45 * scale;
  return {
    x: l.x + (Math.random() * 2 - 1) * r,
    y: l.y + scale * (0.15 + Math.random() * 0.55),
    z: l.z + (Math.random() * 2 - 1) * r,
  };
}

// =========================================================================== ore drops

function enchantLevel(item, id) {
  const ench = safe(() => item?.getComponent("minecraft:enchantable"));
  if (!ench) return 0;
  return safe(() => ench.getEnchantment(id)?.level) ?? safe(() => ench.getEnchantment(`minecraft:${id}`)?.level) ?? 0;
}

world.afterEvents.playerBreakBlock.subscribe((ev) => {
  const id = ev.brokenBlockPermutation?.type?.id ?? "";
  if (!id.endsWith("_ore")) return; // includes lit_redstone_ore and the deepslate / nether ores
  const { player } = ev;
  if (isCreative(player)) return;
  const tool = ev.itemStackBeforeBreak;
  if (enchantLevel(tool, "silk_touch") > 0) return;
  const chance = DROP_CHANCE * (1 + FORTUNE_BONUS * enchantLevel(tool, "fortune"));
  if (Math.random() >= chance) return;

  const l = ev.block.location;
  const at = { x: l.x + 0.5, y: l.y + 0.5, z: l.z + 0.5 };
  safe(() => ev.dimension.spawnItem(new ItemStack(STONE_ID, 1), at));
  safe(() => ev.dimension.spawnParticle("minecraft:villager_happy", at));
  safe(() => ev.dimension.playSound("random.orb", at, { pitch: 1.5, volume: 0.6 }));
  tell(player, "§dYou found an Evolution Stone!");
});

// =========================================================================== evolving

/** playerId -> tick of the last stone use */
const lastUse = new Map();

function onCooldown(player) {
  const now = system.currentTick;
  if (now - (lastUse.get(player.id) ?? -1000) < COOLDOWN_TICKS) return true;
  lastUse.set(player.id, now);
  return false;
}

/** Remove one stone from the held stack (re-read now: the event's copy can be stale). */
function useOneStone(player) {
  if (isCreative(player)) return true;
  const container = player.getComponent("minecraft:inventory")?.container;
  if (!container) return false;
  const slot = player.selectedSlotIndex;
  const item = container.getItem(slot);
  if (item?.typeId !== STONE_ID) return false;
  if (item.amount > 1) {
    item.amount -= 1;
    container.setItem(slot, item);
  } else {
    container.setItem(slot, undefined);
  }
  return true;
}

function evolve(player, cat) {
  if (!cat?.isValid || cat.typeId !== CAT_ID) return;
  if (!cat.getComponent("minecraft:is_tamed")) {
    tell(player, "§7Only a tamed Big Cat can evolve. Tame it with fish first.");
    return;
  }
  const stage = stageOf(cat);
  if (stage >= MAX_STAGE) {
    tell(player, `§f${catName(cat)} is fully evolved (stage ${MAX_STAGE}/${MAX_STAGE}).`);
    return;
  }
  if (!useOneStone(player)) return;

  const next = stage + 1;
  const info = STAGES[next - 1];
  cat.triggerEvent(`mymod:evolve_${next}`);
  // The new health component exists from the next tick on; then top the cat up to its new maximum.
  system.runTimeout(() => {
    if (cat.isValid) safe(() => cat.getComponent("minecraft:health")?.resetToMaxValue());
  }, 2);

  const dim = cat.dimension;
  for (let i = 0; i < BURST_PARTICLES; i++) safe(() => dim.spawnParticle(info.particle, aroundCat(cat)));
  safe(() => dim.playSound("random.levelup", cat.location, { pitch: 0.7 + next * 0.08 }));
  if (next >= WING_STAGE) {
    safe(() => dim.spawnParticle("minecraft:totem_particle", aroundCat(cat)));
    safe(() => dim.playSound("mob.enderdragon.flap", cat.location, { pitch: 1.4 }));
    tell(player, `§d${catName(cat)} grew wings! ${info.color}Stage ${next}: ${info.name}§d. Ride it and jump to fly.`);
  } else {
    tell(player, `§d${catName(cat)} evolved! ${info.color}Stage ${next}/${MAX_STAGE}: ${info.name}`);
  }
}

// Right-clicking a cat: cancel the normal interaction (sit / ride / feed) and evolve instead.
world.beforeEvents.playerInteractWithEntity.subscribe((ev) => {
  if (ev.itemStack?.typeId !== STONE_ID || ev.target?.typeId !== CAT_ID) return;
  ev.cancel = true;
  const { player, target } = ev;
  system.run(() => {
    if (!onCooldown(player)) evolve(player, target);
  });
});

// Using the stone in the air while aiming at a cat (handy for giant cats).
world.afterEvents.itemUse.subscribe((ev) => {
  if (ev.itemStack?.typeId !== STONE_ID) return;
  const player = ev.source;
  if (onCooldown(player)) return;
  const hit = player
    .getEntitiesFromViewDirection({ maxDistance: USE_RANGE })
    .find((h) => h.entity?.isValid && h.entity.typeId === CAT_ID);
  if (hit) evolve(player, hit.entity);
  else tell(player, "§7Use the Evolution Stone on a tamed Big Cat.");
});

// =========================================================================== ambient particles

system.runInterval(() => {
  for (const dimId of DIMENSIONS) {
    const cats = safe(() => world.getDimension(dimId).getEntities({ type: CAT_ID })) ?? [];
    for (const cat of cats) {
      const stage = stageOf(cat);
      if (stage < 1) continue;
      const particle = STAGES[Math.min(stage, MAX_STAGE) - 1].particle;
      safe(() => cat.dimension.spawnParticle(particle, aroundCat(cat)));
    }
  }
}, AURA_INTERVAL_TICKS);

// =========================================================================== flight

/** playerId -> true while they ride a winged cat (to catch them getting off mid-air) */
const flyingRiders = new Map();

function riddenCat(player) {
  const mount = safe(() => player.getComponent("minecraft:riding")?.entityRidingOn);
  return mount?.isValid && mount.typeId === CAT_ID && stageOf(mount) >= WING_STAGE ? mount : undefined;
}

/** Rider input: forward/back in -1..1 and whether jump is held. Missing APIs count as no input. */
function riderInput(player) {
  const info = safe(() => player.inputInfo);
  const move = safe(() => info.getMovementVector()) ?? { x: 0, y: 0 };
  // "Jump" / "Pressed" are the string values of InputButton.Jump / ButtonState.Pressed. Not
  // imported on purpose: a missing named import would stop every script in the pack.
  const jump = safe(() => info.getButtonState("Jump") === "Pressed") ?? safe(() => player.isJumping) ?? false;
  return { forward: move.y ?? 0, jump };
}

function fly(player, cat) {
  const { forward, jump } = riderInput(player);
  const airborne = !cat.isOnGround;
  if (!airborne) {
    // On the ground the cat walks as usual; jump launches it into the air.
    if (jump) safe(() => cat.applyImpulse({ x: 0, y: TAKEOFF_SPEED, z: 0 }));
    return;
  }
  const look = player.getViewDirection();
  let want = { x: 0, y: -SINK_SPEED, z: 0 };
  if (forward > 0.1) want = { x: look.x * FLY_SPEED * forward, y: look.y * FLY_SPEED * forward, z: look.z * FLY_SPEED * forward };
  else if (forward < -0.1) want = { x: look.x * BACK_SPEED * forward, y: 0, z: look.z * BACK_SPEED * forward };
  if (jump) want.y = Math.max(want.y, CLIMB_SPEED);

  const v = cat.getVelocity();
  const next = {
    x: v.x + (want.x - v.x) * STEERING,
    y: v.y + (want.y - v.y) * STEERING + GRAVITY_LIFT,
    z: v.z + (want.z - v.z) * STEERING,
  };
  safe(() => {
    cat.clearVelocity();
    cat.applyImpulse(next);
  });
}

system.runInterval(() => {
  for (const player of world.getAllPlayers()) {
    const cat = riddenCat(player);
    if (cat) {
      flyingRiders.set(player.id, true);
      fly(player, cat);
    } else if (flyingRiders.has(player.id)) {
      flyingRiders.delete(player.id);
      // Got off (or was thrown off) a winged cat: don't let them fall to their death.
      if (!player.isOnGround) {
        safe(() => player.addEffect("slow_falling", DISMOUNT_SLOW_FALL_TICKS, { showParticles: false }));
      }
    }
  }
}, 1);

world.afterEvents.playerLeave.subscribe((ev) => {
  flyingRiders.delete(ev.playerId);
  lastUse.delete(ev.playerId);
});
