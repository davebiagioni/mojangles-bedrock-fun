// Size Wand and Vapor Wand. Hand-written (not generated) - edit freely.
//
// Both wands work the same way:
//   * use (right-click / tap) while aiming at another player within WAND_RANGE: change them,
//   * hit another player with it: change them,
//   * use it anywhere else: change yourself.
// Each use moves to the next setting:
//   Size Wand:  normal -> mini (0.4x) -> huge (2.5x) -> normal
//   Vapor Wand: none -> rainbow sparkles -> stinky green vapor -> none
// Drinking milk puts you back to normal size and clears your vapor.
//
// Size uses the mymod:size_* events that tools/gen_player.py adds to the player entity. Only the
// look changes: hitbox, reach and camera height stay vanilla. Both settings are saved on the
// player as dynamic properties, so they survive relogs and deaths.

import { world, system, MolangVariableMap } from "@minecraft/server";

const SIZE_WAND = "mymod:size_wand";
const VAPOR_WAND = "mymod:vapor_wand";
const PROP_SIZE = "bigcat_size"; // "normal" | "mini" | "huge"
const PROP_VAPOR = "bigcat_vapor"; // "none" | "rainbow" | "stinky"

const WAND_RANGE = 10;
const COOLDOWN_TICKS = 6;
const VAPOR_INTERVAL_TICKS = 4;

const SIZES = ["normal", "mini", "huge"];
const SCALE = { normal: 1, mini: 0.4, huge: 2.5 }; // must match SIZES in tools/gen_player.py
const SIZE_TEXT = { normal: "§fnormal size", mini: "§bmini", huge: "§6HUGE" };

const VAPORS = ["none", "rainbow", "stinky"];
const VAPOR_PARTICLE = { rainbow: "mymod:rainbow_sparkle", stinky: "mymod:stinky_vapor" };
const VAPOR_TEXT = { none: "§fno vapor", rainbow: "§dr§ca§6i§en§ab§bo§9w §dsparkles", stinky: "§2stinky green vapor" };

const lastAction = new Map();

function onCooldown(player) {
  const now = system.currentTick;
  if (now - (lastAction.get(player.id) ?? -1000) < COOLDOWN_TICKS) return true;
  lastAction.set(player.id, now);
  return false;
}

function getSetting(player, prop, values) {
  const v = player.getDynamicProperty(prop);
  return values.includes(v) ? v : values[0];
}

function next(values, current) {
  return values[(values.indexOf(current) + 1) % values.length];
}

function tellChange(actor, target, what) {
  if (actor.id === target.id) {
    actor.onScreenDisplay.setActionBar(`You are now ${what}`);
  } else {
    actor.onScreenDisplay.setActionBar(`${target.name} is now ${what}`);
    target.onScreenDisplay.setActionBar(`${actor.name} made you ${what}`);
  }
}

// --- size --------------------------------------------------------------------------------
function applySize(player, size) {
  player.setDynamicProperty(PROP_SIZE, size);
  player.triggerEvent(`mymod:size_${size}`);
}

function cycleSize(actor, target) {
  const size = next(SIZES, getSetting(target, PROP_SIZE, SIZES));
  applySize(target, size);
  tellChange(actor, target, SIZE_TEXT[size]);
  target.dimension.playSound(size === "mini" ? "random.pop" : size === "huge" ? "mob.irongolem.repair" : "random.orb",
    target.location, { pitch: size === "mini" ? 1.8 : size === "huge" ? 0.6 : 1.0 });
}

// --- vapor -------------------------------------------------------------------------------
function cycleVapor(actor, target) {
  const vapor = next(VAPORS, getSetting(target, PROP_VAPOR, VAPORS));
  target.setDynamicProperty(PROP_VAPOR, vapor);
  tellChange(actor, target, VAPOR_TEXT[vapor]);
  const sound = { none: "random.fizz", rainbow: "random.levelup", stinky: "mob.slime.big" }[vapor];
  target.dimension.playSound(sound, target.location, { volume: 0.6 });
}

system.runInterval(() => {
  for (const player of world.getAllPlayers()) {
    const vapor = getSetting(player, PROP_VAPOR, VAPORS);
    if (vapor === "none") continue;
    const scale = SCALE[getSetting(player, PROP_SIZE, SIZES)];
    const vars = new MolangVariableMap();
    vars.setFloat("variable.size", scale);
    const { x, y, z } = player.location;
    try {
      player.dimension.spawnParticle(VAPOR_PARTICLE[vapor], { x, y: y + 0.9 * scale, z }, vars);
    } catch {
      // chunk not loaded or similar; try again next time
    }
  }
}, VAPOR_INTERVAL_TICKS);

// --- input -------------------------------------------------------------------------------
const ACTIONS = { [SIZE_WAND]: cycleSize, [VAPOR_WAND]: cycleVapor };

function heldWand(player) {
  const item = player.getComponent("minecraft:inventory")?.container?.getItem(player.selectedSlotIndex);
  return ACTIONS[item?.typeId] ? item.typeId : undefined;
}

world.afterEvents.itemUse.subscribe((ev) => {
  const action = ACTIONS[ev.itemStack?.typeId];
  const p = ev.source;
  if (!action || p.typeId !== "minecraft:player" || onCooldown(p)) return;
  const hit = p
    .getEntitiesFromViewDirection({ maxDistance: WAND_RANGE })
    .find((h) => h.entity?.typeId === "minecraft:player" && h.entity.id !== p.id);
  action(p, hit ? hit.entity : p);
});

world.afterEvents.entityHitEntity.subscribe((ev) => {
  const p = ev.damagingEntity;
  if (p?.typeId !== "minecraft:player" || ev.hitEntity?.typeId !== "minecraft:player") return;
  const wand = heldWand(p);
  if (!wand || onCooldown(p)) return;
  ACTIONS[wand](p, ev.hitEntity);
});

// Milk washes it all off.
world.afterEvents.itemCompleteUse.subscribe((ev) => {
  if (ev.itemStack?.typeId !== "minecraft:milk_bucket") return;
  const p = ev.source;
  const changed = getSetting(p, PROP_SIZE, SIZES) !== "normal" || getSetting(p, PROP_VAPOR, VAPORS) !== "none";
  applySize(p, "normal");
  p.setDynamicProperty(PROP_VAPOR, "none");
  if (changed) p.onScreenDisplay.setActionBar("§fThe milk washed it all off");
});

// Make sure the body matches the saved size after joining or respawning.
world.afterEvents.playerSpawn.subscribe((ev) => {
  const size = getSetting(ev.player, PROP_SIZE, SIZES);
  if (size !== "normal") applySize(ev.player, size);
});

world.afterEvents.playerLeave.subscribe((ev) => lastAction.delete(ev.playerId));
