// Gear add-on: Amethyst armor set bonus + Geode Goggles night vision.
// Hand-written source (not generated). API: @minecraft/server 2.11.0.
//
// Every TICK_INTERVAL ticks, for each player:
//   * all four amethyst pieces worn  -> SET_EFFECTS (refreshed), chime + sparkle + actionbar on activation
//   * Geode Goggles worn on the head -> GOGGLE_EFFECTS (refreshed), actionbar on equip
// State lives in entity tags (prefixed gear_) so messages fire only on change, also across rejoins.

import { system, world, EquipmentSlot, EntityComponentTypes } from "@minecraft/server";

const TICK_INTERVAL = 20;

const SET_PIECES = [
  [EquipmentSlot.Head, "gear:amethyst_helmet"],
  [EquipmentSlot.Chest, "gear:amethyst_chestplate"],
  [EquipmentSlot.Legs, "gear:amethyst_leggings"],
  [EquipmentSlot.Feet, "gear:amethyst_boots"],
];
const GOGGLES = "gear:geode_goggles";

const SET_TAG = "gear_amethyst_set";
const GOGGLES_TAG = "gear_goggles";

// Effects are short and refreshed every TICK_INTERVAL, so they drop off ~1-2 s after a piece
// comes off (and are also removed straight away). `amp` is the level minus one (1 = II).
const SET_EFFECTS = [
  { id: "minecraft:resistance", amp: 2 }, // III: 60% less damage
  { id: "minecraft:strength", amp: 1 }, // II
  { id: "minecraft:speed", amp: 1 }, // II
  { id: "minecraft:haste", amp: 1 }, // II
  { id: "minecraft:regeneration", amp: 1 }, // II
  { id: "minecraft:jump_boost", amp: 0 }, // I
  { id: "minecraft:fire_resistance", amp: 0 },
  { id: "minecraft:water_breathing", amp: 0 },
].map((e) => ({ ...e, ticks: 60, refreshBelow: TICK_INTERVAL + 5 }));
// Night vision flickers during its last 10 s (200 ticks), so keep it well above that.
const GOGGLE_EFFECTS = [
  { id: "minecraft:night_vision", amp: 0, ticks: 400, refreshBelow: 300 },
  { id: "minecraft:water_breathing", amp: 0, ticks: 60, refreshBelow: TICK_INTERVAL + 5 },
];

function equippedId(equippable, slot) {
  const item = equippable.getEquipment(slot);
  return item ? item.typeId : undefined;
}

// Add/refresh an effect we own, without overriding a stronger or longer one from a potion/beacon.
function refreshEffect(player, e) {
  const current = player.getEffect(e.id);
  if (current && (current.amplifier > e.amp || (current.amplifier === e.amp && current.duration > e.refreshBelow))) return;
  player.addEffect(e.id, e.ticks, { amplifier: e.amp, showParticles: false });
}

// Remove an effect only if it still looks like ours (same level, no longer than we ever give it).
function clearOwnEffect(player, e) {
  const current = player.getEffect(e.id);
  if (current && current.amplifier === e.amp && current.duration <= e.ticks) {
    player.removeEffect(e.id);
  }
}

function sparkle(player) {
  const { x, y, z } = player.location;
  const dim = player.dimension;
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2;
    dim.spawnParticle("minecraft:villager_happy", { x: x + Math.cos(a) * 0.8, y: y + 1.0, z: z + Math.sin(a) * 0.8 });
  }
  dim.spawnParticle("minecraft:totem_particle", { x, y: y + 1.2, z });
}

function updatePlayer(player) {
  const equippable = player.getComponent(EntityComponentTypes.Equippable);
  if (!equippable) return;

  // --- Amethyst set bonus ---------------------------------------------------
  const fullSet = SET_PIECES.every(([slot, id]) => equippedId(equippable, slot) === id);
  const hadSet = player.hasTag(SET_TAG);
  if (fullSet) {
    for (const e of SET_EFFECTS) refreshEffect(player, e);
    if (!hadSet) {
      player.addTag(SET_TAG);
      player.onScreenDisplay.setActionBar({ translate: "gear.set_bonus.on" });
      player.playSound("chime.amethyst_block", { volume: 1.0, pitch: 1.2 });
      sparkle(player);
    }
  } else if (hadSet) {
    player.removeTag(SET_TAG);
    for (const e of SET_EFFECTS) clearOwnEffect(player, e);
    player.onScreenDisplay.setActionBar({ translate: "gear.set_bonus.off" });
    player.playSound("chime.amethyst_block", { volume: 0.6, pitch: 0.7 });
  }

  // --- Geode Goggles --------------------------------------------------------
  const goggles = equippedId(equippable, EquipmentSlot.Head) === GOGGLES;
  const hadGoggles = player.hasTag(GOGGLES_TAG);
  if (goggles) {
    for (const e of GOGGLE_EFFECTS) refreshEffect(player, e);
    if (!hadGoggles) {
      player.addTag(GOGGLES_TAG);
      player.onScreenDisplay.setActionBar({ translate: "gear.goggles.on" });
      player.playSound("chime.amethyst_block", { volume: 0.8, pitch: 1.5 });
    }
  } else if (hadGoggles) {
    player.removeTag(GOGGLES_TAG);
    // Keep anything the full set is also giving right now (e.g. water breathing).
    for (const e of GOGGLE_EFFECTS) {
      if (!(fullSet && SET_EFFECTS.some((s) => s.id === e.id))) clearOwnEffect(player, e);
    }
    player.onScreenDisplay.setActionBar({ translate: "gear.goggles.off" });
  }
}

// Purple flames (gear_rp/particles/amethyst_flame.particle.json) around anyone wearing the full
// set. The set tag is kept in sync by updatePlayer below.
const FLAME_INTERVAL = 2; // ticks
const FLAMES_PER_BURST = 3;

function purpleFlames(player) {
  const { x, y, z } = player.location;
  const dim = player.dimension;
  for (let i = 0; i < FLAMES_PER_BURST; i++) {
    const a = Math.random() * Math.PI * 2;
    const r = 0.35 + Math.random() * 0.2;
    // mostly around the legs and body, a few at the feet
    const h = Math.random() < 0.3 ? 0.05 : 0.2 + Math.random() * 1.4;
    dim.spawnParticle("gear:amethyst_flame", { x: x + Math.cos(a) * r, y: y + h, z: z + Math.sin(a) * r });
  }
}

system.runInterval(() => {
  for (const player of world.getAllPlayers()) {
    if (!player.isValid || !player.hasTag(SET_TAG)) continue;
    try {
      purpleFlames(player);
    } catch {
      // player in an unloaded chunk or changing dimension; try again next burst
    }
  }
}, FLAME_INTERVAL);

system.runInterval(() => {
  for (const player of world.getAllPlayers()) {
    if (!player.isValid) continue;
    try {
      updatePlayer(player);
    } catch (e) {
      console.warn(`[gear] update failed for ${player.name}: ${e}`);
    }
  }
}, TICK_INTERVAL);
