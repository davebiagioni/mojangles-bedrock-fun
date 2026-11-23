// Morph Wand. Hand-written (not generated) - edit freely. The list of creatures is generated:
// see FORMS in tools/gen_morph.py (-> scripts/morph_forms.js).
//
// Like the Size and Vapor Wands:
//   * use (right-click / tap) while aiming at another player within WAND_RANGE: change them,
//   * hit another player with it: change them,
//   * use it anywhere else: change yourself.
// Each use turns the player into the next creature; after the last one they're themselves again.
// Sneak + use: straight back to yourself. Drinking milk does the same.
//
// The costume: the player gets Invisibility and a mymod:morph_<form> entity (no AI, can't be hurt, too
// small to click) is moved onto them every tick. Invisibility doesn't hide armour, so while
// morphed the armour is moved into the inventory (marked with ARMOR_MARK in its lore) and put back
// on when the player is themselves again. The item in hand still shows. Each creature also has a
// perk (PERKS below). The form is saved on the player, so it survives relogs and deaths.

import { world, system, EquipmentSlot } from "@minecraft/server";
import { FORMS, MORPH_FAMILY } from "./morph_forms.js";

const WAND = "mymod:morph_wand";
const PROP_FORM = "bigcat_form"; // index into FORMS; 0 = yourself

const WAND_RANGE = 10;
const COOLDOWN_TICKS = 6;
const PERK_INTERVAL = 20;
const PERK_DURATION = 260; // > 200, so Night Vision never starts to flicker
const SWEEP_INTERVAL = 40;
const CREEPER_FUSE_TICKS = 30; // sneak this long as a creeper: harmless BOOM
const ARMOR_SLOTS = [EquipmentSlot.Head, EquipmentSlot.Chest, EquipmentSlot.Legs, EquipmentSlot.Feet];
const ARMOR_MARK = "§8Morph Wand: worn on "; // + slot name; how we find the armour to put back on
const DIMENSIONS = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"];

// effect id -> amplifier (0 = level I). Invisibility is added for every form.
const PERKS = {
  chicken: { slow_falling: 0 },
  pig: { saturation: 0 },
  fox: { night_vision: 0, speed: 0 },
  frog: { jump_boost: 2 },
  bee: { slow_falling: 0 }, // + hold jump to fly up (see flyBees)
  creeper: {},
  iron_golem: { strength: 1, resistance: 1, slowness: 0 },
  big_cat: { speed: 1, jump_boost: 0 },
};
const PERK_TEXT = {
  chicken: "you float down gently",
  pig: "you never get hungry",
  fox: "fast, and you can see in the dark",
  frog: "super jumps",
  bee: "hold jump to fly",
  creeper: "sneak to go BOOM (it doesn't hurt)",
  iron_golem: "strong and tough, but slow",
  big_cat: "fast and bouncy",
};

/** playerId -> costume entity */
const costumes = new Map();
const lastAction = new Map();
/** playerId -> tick the creeper started sneaking (undefined once it went boom) */
const fuseStart = new Map();

function safe(fn) {
  try {
    return fn();
  } catch {
    return undefined;
  }
}

function formOf(player) {
  const n = safe(() => player.getDynamicProperty(PROP_FORM));
  return Number.isInteger(n) && n > 0 && n < FORMS.length ? n : 0;
}

function clearPerks(player, n) {
  const effects = n > 0 ? ["invisibility", ...Object.keys(PERKS[FORMS[n].key] ?? {})] : [];
  if (FORMS[n]?.key === "bee") effects.push("levitation");
  for (const id of effects) safe(() => player.removeEffect(`minecraft:${id}`));
}

const warned = new Set();

// Effect ids need the "minecraft:" prefix: addEffect can quietly refuse a bare name (it returns
// undefined instead of throwing). If it refuses anyway, fall back to the /effect command.
function addEffect(player, id, amplifier) {
  const full = id.includes(":") ? id : `minecraft:${id}`;
  let added;
  try {
    added = player.addEffect(full, PERK_DURATION, { amplifier, showParticles: false });
  } catch (e) {
    added = e;
  }
  if (added && !(added instanceof Error)) return;
  const ok = safe(() => player.runCommand(`effect @s ${id} ${Math.ceil(PERK_DURATION / 20)} ${amplifier} true`));
  if (!warned.has(id)) console.warn(`[bigcat morph] addEffect(${full}) gave ${added}; /effect fallback ${ok ? "worked" : "failed"}`);
  warned.add(id);
}

function givePerks(player, n) {
  addEffect(player, "invisibility", 0);
  for (const [id, amplifier] of Object.entries(PERKS[FORMS[n].key] ?? {})) addEffect(player, id, amplifier);
}

// --------------------------------------------------------------------------- armour

/** Move worn armour into the inventory. Pieces that don't fit stay on (and show). */
function stashArmor(player) {
  const eq = safe(() => player.getComponent("minecraft:equippable"));
  const inv = safe(() => player.getComponent("minecraft:inventory").container);
  if (!eq || !inv) return;
  let full = false;
  for (const slot of ARMOR_SLOTS) {
    const item = safe(() => eq.getEquipment(slot));
    if (!item) continue;
    if (inv.emptySlotsCount === 0) {
      full = true;
      continue;
    }
    item.setLore([...item.getLore().filter((l) => !l.startsWith(ARMOR_MARK)), ARMOR_MARK + slot]);
    if (inv.addItem(item) === undefined) eq.setEquipment(slot, undefined);
  }
  if (full) safe(() => player.onScreenDisplay.setActionBar("§eInventory full: some armour stays on and shows"));
}

/** Put marked armour back on (if that slot is free) and remove the mark. */
function restoreArmor(player) {
  const eq = safe(() => player.getComponent("minecraft:equippable"));
  const inv = safe(() => player.getComponent("minecraft:inventory").container);
  if (!eq || !inv) return;
  for (let i = 0; i < inv.size; i++) {
    const item = inv.getItem(i);
    const lore = item?.getLore() ?? [];
    const mark = lore.find((l) => l.startsWith(ARMOR_MARK));
    if (!mark) continue;
    const slot = mark.slice(ARMOR_MARK.length);
    item.setLore(lore.filter((l) => l !== mark));
    if (ARMOR_SLOTS.includes(slot) && !safe(() => eq.getEquipment(slot))) {
      eq.setEquipment(slot, item);
      inv.setItem(i, undefined);
    } else {
      inv.setItem(i, item);
    }
  }
}

function removeCostume(playerId) {
  const c = costumes.get(playerId);
  costumes.delete(playerId);
  if (c?.isValid) safe(() => c.remove());
}

function setForm(actor, target, n) {
  const old = formOf(target);
  clearPerks(target, old);
  target.setDynamicProperty(PROP_FORM, n === 0 ? undefined : n);
  fuseStart.delete(target.id);
  if (n === 0) {
    removeCostume(target.id);
    safe(() => restoreArmor(target));
  } else {
    givePerks(target, n);
    safe(() => stashArmor(target));
  }

  const f = FORMS[n];
  const dim = target.dimension;
  const at = { x: target.location.x, y: target.location.y + 1, z: target.location.z };
  safe(() => dim.playSound(f.sound, at, { pitch: f.pitch }));
  safe(() => dim.playSound("random.pop", at, { pitch: 0.8 }));
  for (let i = 0; i < 12; i++) {
    const p = { x: at.x + (Math.random() - 0.5) * 1.4, y: at.y + (Math.random() - 0.5) * 1.6, z: at.z + (Math.random() - 0.5) * 1.4 };
    safe(() => dim.spawnParticle("minecraft:villager_happy", p));
  }
  const what = n === 0 ? f.name : `${f.name}! §7(${PERK_TEXT[f.key]})`;
  if (actor.id === target.id) {
    safe(() => actor.onScreenDisplay.setActionBar(`You are ${what}`));
  } else {
    safe(() => actor.onScreenDisplay.setActionBar(`${target.name} is now ${f.name}`));
    safe(() => target.onScreenDisplay.setActionBar(`${actor.name} turned you into ${what}`));
  }
}

function useWand(actor, target) {
  const n = actor.isSneaking ? 0 : (formOf(target) + 1) % FORMS.length;
  setForm(actor, target, n);
}

// --------------------------------------------------------------------------- input

function onCooldown(player) {
  const now = system.currentTick;
  if (now - (lastAction.get(player.id) ?? -1000) < COOLDOWN_TICKS) return true;
  lastAction.set(player.id, now);
  return false;
}

world.afterEvents.itemUse.subscribe((ev) => {
  const p = ev.source;
  if (ev.itemStack?.typeId !== WAND || p.typeId !== "minecraft:player" || onCooldown(p)) return;
  const hit = safe(() => p.getEntitiesFromViewDirection({ maxDistance: WAND_RANGE }))?.find(
    (h) => h.entity?.typeId === "minecraft:player" && h.entity.id !== p.id,
  );
  useWand(p, hit ? hit.entity : p);
});

world.afterEvents.entityHitEntity.subscribe((ev) => {
  const p = ev.damagingEntity;
  if (p?.typeId !== "minecraft:player" || ev.hitEntity?.typeId !== "minecraft:player") return;
  const item = safe(() => p.getComponent("minecraft:inventory").container.getItem(p.selectedSlotIndex));
  if (item?.typeId !== WAND || onCooldown(p)) return;
  useWand(p, ev.hitEntity);
});

world.afterEvents.itemCompleteUse.subscribe((ev) => {
  if (ev.itemStack?.typeId !== "minecraft:milk_bucket" || formOf(ev.source) === 0) return;
  setForm(ev.source, ev.source, 0);
});

world.afterEvents.playerLeave.subscribe((ev) => {
  removeCostume(ev.playerId);
  lastAction.delete(ev.playerId);
  fuseStart.delete(ev.playerId);
});

// --------------------------------------------------------------------------- the costume follows

function follow(player, n) {
  const dead = (safe(() => player.getComponent("minecraft:health").currentValue) ?? 1) <= 0;
  let c = costumes.get(player.id);
  if (dead) {
    removeCostume(player.id);
    return;
  }
  const type = FORMS[n].entity; // one entity type per creature (see tools/gen_morph.py)
  if (c && (!c.isValid || c.dimension.id !== player.dimension.id || c.typeId !== type)) {
    removeCostume(player.id);
    c = undefined;
  }
  const rotation = player.getRotation();
  if (!c) {
    c = safe(() => player.dimension.spawnEntity(type, player.location));
    if (!c) return;
    costumes.set(player.id, c);
  }
  safe(() => c.teleport(player.location, { rotation, keepVelocity: false }));
}

function flyBee(player) {
  const info = safe(() => player.inputInfo);
  const jump = safe(() => info.getButtonState("Jump") === "Pressed") ?? safe(() => player.isJumping) ?? false;
  if (jump) safe(() => player.addEffect("minecraft:levitation", 3, { amplifier: 3, showParticles: false }));
}

function creeperFuse(player) {
  const now = system.currentTick;
  if (!player.isSneaking) {
    fuseStart.delete(player.id);
    return;
  }
  if (!fuseStart.has(player.id)) {
    fuseStart.set(player.id, now);
    safe(() => player.dimension.playSound("random.fuse", player.location));
    return;
  }
  const start = fuseStart.get(player.id);
  if (start === undefined || now - start < CREEPER_FUSE_TICKS) return;
  fuseStart.set(player.id, undefined); // one boom per sneak
  const at = { x: player.location.x, y: player.location.y + 0.8, z: player.location.z };
  safe(() => player.dimension.spawnParticle("minecraft:huge_explosion_emitter", at));
  safe(() => player.dimension.playSound("random.explode", at));
}

system.runInterval(() => {
  const refresh = system.currentTick % PERK_INTERVAL === 0;
  for (const player of world.getAllPlayers()) {
    const n = formOf(player);
    if (n === 0) {
      if (costumes.has(player.id)) removeCostume(player.id);
      continue;
    }
    follow(player, n);
    if (refresh) {
      givePerks(player, n);
      safe(() => stashArmor(player)); // armour put on while morphed
    }
    if (FORMS[n].key === "bee") flyBee(player);
    if (FORMS[n].key === "creeper") creeperFuse(player);
  }
}, 1);

// Costumes nobody owns (left over from a reload or a crash) are removed.
system.runInterval(() => {
  const owned = new Set([...costumes.values()].filter((c) => c.isValid).map((c) => c.id));
  for (const id of DIMENSIONS) {
    const dim = safe(() => world.getDimension(id));
    for (const c of safe(() => dim.getEntities({ families: [MORPH_FAMILY] })) ?? []) {
      if (!owned.has(c.id)) safe(() => c.remove());
    }
  }
}, SWEEP_INTERVAL);
