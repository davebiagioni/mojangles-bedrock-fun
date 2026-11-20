// Gear add-on: Amethyst armor set bonus + Geode Goggles night vision.
// Hand-written source (not generated). API: @minecraft/server 2.11.0.
//
// Every TICK_INTERVAL ticks, for each player:
//   * all four amethyst pieces worn  -> Resistance I (refreshed), chime + sparkle + actionbar on activation
//   * Geode Goggles worn on the head -> Night Vision (refreshed), actionbar on equip
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

// Resistance: short duration, refreshed every interval, so it drops off ~2s after a piece is removed.
const RESISTANCE = "minecraft:resistance";
const RESISTANCE_TICKS = 50;
// Night vision flickers during its last 10 s (200 ticks), so keep it well above that.
const NIGHT_VISION = "minecraft:night_vision";
const NIGHT_VISION_TICKS = 400;
const NIGHT_VISION_REFRESH_BELOW = 300;

function equippedId(equippable, slot) {
  const item = equippable.getEquipment(slot);
  return item ? item.typeId : undefined;
}

// Add/refresh an effect we own, without overriding a stronger or longer one from a potion/beacon.
function refreshEffect(player, effectId, ticks, refreshBelow) {
  const current = player.getEffect(effectId);
  if (current && (current.amplifier > 0 || current.duration > refreshBelow)) return;
  player.addEffect(effectId, ticks, { amplifier: 0, showParticles: false });
}

// Remove an effect only if it still looks like ours (level I, no longer than we ever give it).
function clearOwnEffect(player, effectId, maxTicks) {
  const current = player.getEffect(effectId);
  if (current && current.amplifier === 0 && current.duration <= maxTicks) {
    player.removeEffect(effectId);
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
    refreshEffect(player, RESISTANCE, RESISTANCE_TICKS, TICK_INTERVAL + 5);
    if (!hadSet) {
      player.addTag(SET_TAG);
      player.onScreenDisplay.setActionBar({ translate: "gear.set_bonus.on" });
      player.playSound("chime.amethyst_block", { volume: 1.0, pitch: 1.2 });
      sparkle(player);
    }
  } else if (hadSet) {
    player.removeTag(SET_TAG);
    clearOwnEffect(player, RESISTANCE, RESISTANCE_TICKS);
    player.onScreenDisplay.setActionBar({ translate: "gear.set_bonus.off" });
    player.playSound("chime.amethyst_block", { volume: 0.6, pitch: 0.7 });
  }

  // --- Geode Goggles --------------------------------------------------------
  const goggles = equippedId(equippable, EquipmentSlot.Head) === GOGGLES;
  const hadGoggles = player.hasTag(GOGGLES_TAG);
  if (goggles) {
    refreshEffect(player, NIGHT_VISION, NIGHT_VISION_TICKS, NIGHT_VISION_REFRESH_BELOW);
    if (!hadGoggles) {
      player.addTag(GOGGLES_TAG);
      player.onScreenDisplay.setActionBar({ translate: "gear.goggles.on" });
      player.playSound("chime.amethyst_block", { volume: 0.8, pitch: 1.5 });
    }
  } else if (hadGoggles) {
    player.removeTag(GOGGLES_TAG);
    clearOwnEffect(player, NIGHT_VISION, NIGHT_VISION_TICKS);
    player.onScreenDisplay.setActionBar({ translate: "gear.goggles.off" });
  }
}

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
