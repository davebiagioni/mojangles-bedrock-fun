// Gear add-on: Amethyst armor set bonus + Geode Goggles night vision.
// Hand-written source (not generated). API: @minecraft/server 2.11.0.
//
// Every TICK_INTERVAL ticks, for each player:
//   * all four amethyst pieces worn  -> SET_EFFECTS (refreshed), chime + sparkle + actionbar on activation
//   * Geode Goggles worn on the head -> GOGGLE_EFFECTS (refreshed), actionbar on equip
//   * every gear piece in the inventory or worn -> max-level ENCHANTS added (shows the glint)
// State lives in entity tags (prefixed gear_) so messages fire only on change, also across rejoins.

import { system, world, EquipmentSlot, EntityComponentTypes, EnchantmentTypes } from "@minecraft/server";

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

// Max-level enchantments every gear piece gets automatically (vanilla maximums: the game refuses
// anything higher). Per piece kind; ALL applies to every piece. Incompatible or unsupported ones
// are skipped, so the list can be generous.
const ENCHANTS = {
  ALL: [
    { type: "minecraft:protection", level: 4 },
    { type: "minecraft:unbreaking", level: 3 },
    { type: "minecraft:mending", level: 1 },
    { type: "minecraft:thorns", level: 3 },
  ],
  "gear:amethyst_helmet": [
    { type: "minecraft:respiration", level: 3 },
    { type: "minecraft:aqua_affinity", level: 1 },
  ],
  "gear:geode_goggles": [
    { type: "minecraft:respiration", level: 3 },
    { type: "minecraft:aqua_affinity", level: 1 },
  ],
  "gear:amethyst_chestplate": [],
  "gear:amethyst_leggings": [{ type: "minecraft:swift_sneak", level: 3 }],
  "gear:amethyst_boots": [
    { type: "minecraft:feather_falling", level: 4 },
    { type: "minecraft:depth_strider", level: 3 },
    { type: "minecraft:soul_speed", level: 3 },
  ],
};
const ARMOR_SLOTS = [EquipmentSlot.Head, EquipmentSlot.Chest, EquipmentSlot.Legs, EquipmentSlot.Feet];

/** Adds any missing ENCHANTS to a gear item. Returns true if the item changed. */
function enchantGear(item) {
  const extra = item && ENCHANTS[item.typeId];
  if (!extra) return false;
  const ench = item.getComponent("minecraft:enchantable");
  if (!ench) return false;
  let changed = false;
  for (const e of [...ENCHANTS.ALL, ...extra]) {
    const type = EnchantmentTypes.get(e.type);
    if (!type || ench.hasEnchantment(type)) continue;
    const want = { type, level: Math.min(e.level, type.maxLevel) };
    try {
      if (ench.canAddEnchantment(want)) {
        ench.addEnchantment(want);
        changed = true;
      }
    } catch {
      // not allowed on this slot or clashes with an existing enchantment: skip it
    }
  }
  return changed;
}

/** Enchants gear in the player's inventory and armor slots (writes back only what changed). */
function enchantPlayerGear(player, equippable) {
  const container = player.getComponent("minecraft:inventory")?.container;
  if (container) {
    for (let i = 0; i < container.size; i++) {
      const item = container.getItem(i);
      if (item && enchantGear(item)) container.setItem(i, item);
    }
  }
  for (const slot of ARMOR_SLOTS) {
    const item = equippable.getEquipment(slot);
    if (item && enchantGear(item)) equippable.setEquipment(slot, item);
  }
}

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

  enchantPlayerGear(player, equippable);

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
