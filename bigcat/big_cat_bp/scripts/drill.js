// Mooshroom Drill. Hand-written (not generated) - edit freely.
//
// Use the mymod:mooshroom_drill item on a block to put down a mymod:mooshroom_drill_vehicle: a
// tracked digger with a real mooshroom on the front as its drill bit (the model and the spin
// animation are in the resource pack; tools/gen_mooshroom_drill.py makes the chassis model).
// Get in by using it (right-click / tap). Drive with the normal movement controls; sneak to get
// out. Sneak and hit it to pick it back up. Nothing can hurt it, mooshroom included.
//
// While the driver holds forward, the mooshroom spins (the client-synced mymod:drilling
// property starts the spin animation) and a tunnel TUNNEL_WIDTH wide and TUNNEL_HEIGHT tall is
// carved around and ahead of the drill, every tick. Where the driver looks decides the shape:
//   look level           a flat tunnel
//   look up              a staircase going up (the drill can step up one block)
//   look down            a staircase going down
//   look straight down   a shaft straight down
// Ores go straight into the driver's inventory (as if mined with a plain pickaxe); everything
// else is removed without drops, so the tunnel doesn't fill with items. Like the Laser Blaster,
// it never breaks unbreakable blocks (bedrock, portals, command blocks...) or anything that holds
// items (chests, furnaces...), and leaves water and lava alone. The driver gets night vision,
// fire resistance and water breathing while riding.

import { world, system, ItemStack } from "@minecraft/server";

const ITEM_ID = "mymod:mooshroom_drill";
const VEHICLE_ID = "mymod:mooshroom_drill_vehicle";
const DRILLING = "mymod:drilling";

const PLACE_RANGE = 8; // blocks
const COOLDOWN_TICKS = 5; // also de-duplicates itemUse + playerInteractWithBlock
const TUNNEL_WIDTH = 5;
const TUNNEL_HEIGHT = 5;
const AHEAD = 4.5; // carve this far in front of the vehicle's centre (the bit reaches ~1.4)
const BEHIND = 3.5; // ... and this far behind it, so the chassis can turn around in the tunnel
const STEP_AT = 1.3; // stairs: the floor steps up/down this far ahead of the centre
const SHAFT_DEPTH = 2; // straight down: carve this far below the wheels each tick
const MAX_PER_TICK = 300; // blocks carved per drill per tick, at most
const LEVEL_PITCH = 25; // degrees: looking within this of level digs a flat tunnel
const SHAFT_PITCH = 65; // degrees down: steeper than this digs a shaft
const PERK_TICKS = 300; // driver's effects last this long, refreshed every second
const DIMENSIONS = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"];

// Same list as blaster.js: never carve these.
const UNBREAKABLE = new Set([
  "minecraft:bedrock",
  "minecraft:barrier",
  "minecraft:command_block",
  "minecraft:chain_command_block",
  "minecraft:repeating_command_block",
  "minecraft:structure_block",
  "minecraft:structure_void",
  "minecraft:jigsaw",
  "minecraft:end_portal",
  "minecraft:end_portal_frame",
  "minecraft:end_gateway",
  "minecraft:portal",
  "minecraft:reinforced_deepslate",
  "minecraft:allow",
  "minecraft:deny",
  "minecraft:border_block",
  "minecraft:light_block",
]);

// ore (without "deepslate_" / "lit_") -> [item, min, max]
const ORES = {
  "minecraft:coal_ore": ["minecraft:coal", 1, 1],
  "minecraft:iron_ore": ["minecraft:raw_iron", 1, 1],
  "minecraft:copper_ore": ["minecraft:raw_copper", 2, 5],
  "minecraft:gold_ore": ["minecraft:raw_gold", 1, 1],
  "minecraft:redstone_ore": ["minecraft:redstone", 4, 5],
  "minecraft:lapis_ore": ["minecraft:lapis_lazuli", 4, 9],
  "minecraft:diamond_ore": ["minecraft:diamond", 1, 1],
  "minecraft:emerald_ore": ["minecraft:emerald", 1, 1],
  "minecraft:nether_gold_ore": ["minecraft:gold_nugget", 2, 6],
  "minecraft:quartz_ore": ["minecraft:quartz", 1, 1],
  "minecraft:ancient_debris": ["minecraft:ancient_debris", 1, 1],
  "minecraft:amethyst_cluster": ["minecraft:amethyst_shard", 4, 4],
  "mymod:atomic_bomb": ["mymod:atomic_bomb", 1, 1], // don't eat someone's bomb
};

/** playerId -> tick of last accepted use */
const lastUse = new Map();
/** vehicleId -> vehicle, for drills whose mymod:drilling is on */
const spinning = new Map();

function safe(fn) {
  try {
    return fn();
  } catch {
    return undefined;
  }
}

const randInt = (lo, hi) => lo + Math.floor(Math.random() * (hi - lo + 1));

function oreDrop(typeId) {
  const plain = typeId.replace("deepslate_", "").replace("lit_", "");
  const ore = ORES[plain] ?? ORES[typeId];
  return ore ? new ItemStack(ore[0], randInt(ore[1], ore[2])) : undefined;
}

function canCarve(block) {
  if (!block || block.isAir || block.isLiquid || UNBREAKABLE.has(block.typeId)) return false;
  return !safe(() => block.getComponent("minecraft:inventory")); // chests, furnaces, hoppers...
}

function give(player, stack) {
  const leftover = safe(() => player.getComponent("minecraft:inventory").container.addItem(stack));
  if (leftover) safe(() => player.dimension.spawnItem(leftover, player.location));
}

// --- digging ----------------------------------------------------------------------------------

/** "level" | "up" | "down" | "shaft", from where the driver looks. */
function modeFor(view) {
  const pitchDown = (Math.asin(Math.max(-1, Math.min(1, -view.y))) * 180) / Math.PI;
  if (pitchDown >= SHAFT_PITCH) return "shaft";
  if (pitchDown >= LEVEL_PITCH) return "down";
  if (pitchDown <= -LEVEL_PITCH) return "up";
  return "level";
}

/** Height range [lo, hi) above the wheels to carve at distance t ahead, or undefined for none. */
function heightRange(mode, t) {
  if (mode === "shaft") return [-SHAFT_DEPTH, TUNNEL_HEIGHT];
  const floor = t > STEP_AT ? (mode === "up" ? 1 : mode === "down" ? -1 : 0) : 0;
  return [floor, floor + TUNNEL_HEIGHT];
}

/** Carve the tunnel around `vehicle`. Returns { carved, ores } for effects. */
function carve(vehicle, driver, mode) {
  const dim = vehicle.dimension;
  const at = vehicle.location;
  let f = safe(() => vehicle.getViewDirection()) ?? driver.getViewDirection();
  let fl = Math.hypot(f.x, f.z);
  if (fl < 0.1) {
    f = driver.getViewDirection();
    fl = Math.hypot(f.x, f.z) || 1;
  }
  const fx = f.x / fl;
  const fz = f.z / fl;
  const half = TUNNEL_WIDTH / 2;
  const [t0, t1] = mode === "shaft" ? [-BEHIND, half] : [-BEHIND, AHEAD];

  // bounding box of the carved region (corners of the rotated rectangle)
  let minX = Infinity;
  let maxX = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;
  for (const t of [t0, t1]) {
    for (const l of [-half, half]) {
      const x = at.x + fx * t - fz * l;
      const z = at.z + fz * t + fx * l;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minZ = Math.min(minZ, z);
      maxZ = Math.max(maxZ, z);
    }
  }
  const yLo = Math.floor(at.y) - SHAFT_DEPTH - 1;
  const yHi = Math.floor(at.y) + TUNNEL_HEIGHT + 2;

  let carved = 0;
  let ores = 0;
  for (let bx = Math.floor(minX); bx <= Math.floor(maxX); bx++) {
    for (let bz = Math.floor(minZ); bz <= Math.floor(maxZ); bz++) {
      const rx = bx + 0.5 - at.x;
      const rz = bz + 0.5 - at.z;
      const t = rx * fx + rz * fz; // ahead (+) / behind (-)
      const l = -rx * fz + rz * fx; // sideways
      if (t < t0 || t > t1 || Math.abs(l) > half) continue;
      const [lo, hi] = heightRange(mode, t);
      for (let by = yLo; by <= yHi; by++) {
        const h = by + 0.5 - at.y; // block centre, above the wheels
        if (h < lo || h > hi) continue;
        const block = safe(() => dim.getBlock({ x: bx, y: by, z: bz }));
        if (!canCarve(block)) continue;
        const drop = oreDrop(block.typeId);
        if (safe(() => (block.setType("minecraft:air"), true))) {
          carved++;
          if (drop) {
            ores++;
            give(driver, drop);
          }
          if (carved >= MAX_PER_TICK) return { carved, ores };
        }
      }
    }
  }
  return { carved, ores };
}

function wantsToDrill(driver) {
  // Raw input: only drill while the driver pushes forward, so sitting still and looking around
  // doesn't eat the scenery. Older game versions without inputInfo: drill whenever ridden.
  const move = safe(() => driver.inputInfo.getMovementVector());
  return move ? move.y > 0.3 : true;
}

function setDrilling(vehicle, on) {
  if (on) spinning.set(vehicle.id, vehicle);
  else spinning.delete(vehicle.id);
  if (safe(() => vehicle.getProperty(DRILLING)) !== on) safe(() => vehicle.setProperty(DRILLING, on));
}

function drillTick(tick) {
  const active = new Set();
  for (const driver of world.getAllPlayers()) {
    const vehicle = safe(() => driver.getComponent("minecraft:riding")?.entityRidingOn);
    if (vehicle?.typeId !== VEHICLE_ID || !vehicle.isValid) continue;
    // the driver's cab perks
    if (tick % 20 === 0) {
      for (const effect of ["night_vision", "fire_resistance", "water_breathing"]) {
        safe(() => driver.addEffect(effect, PERK_TICKS, { amplifier: 0, showParticles: false }));
      }
    }
    if (!wantsToDrill(driver)) continue;
    active.add(vehicle.id);
    setDrilling(vehicle, true);
    const mode = modeFor(driver.getViewDirection());
    const { carved, ores } = carve(vehicle, driver, mode);

    const dim = vehicle.dimension;
    const v = safe(() => vehicle.getViewDirection()) ?? { x: 0, y: 0, z: 0 };
    const nose = { x: vehicle.location.x + v.x * 1.8, y: vehicle.location.y + 1.8, z: vehicle.location.z + v.z * 1.8 };
    if (tick % 2 === 0) safe(() => dim.spawnParticle("minecraft:mycelium_dust_particle", nose));
    if (carved > 0) {
      safe(() => dim.spawnParticle("minecraft:critical_hit_emitter", nose));
      if (tick % 4 === 0) safe(() => dim.playSound("dig.stone", nose, { volume: 0.8, pitch: 0.6 + Math.random() * 0.3 }));
    }
    if (ores > 0) safe(() => dim.playSound("random.orb", driver.location, { volume: 0.4, pitch: 1.2 + Math.random() * 0.4 }));
    if (tick % 10 === 0) safe(() => dim.playSound("minecart.base", nose, { volume: 0.5, pitch: 1.6 }));
    if (Math.random() < 0.006) safe(() => dim.playSound("mob.cow.say", nose, { volume: 1.0, pitch: 1.4 }));
  }
  for (const [id, vehicle] of spinning) {
    if (active.has(id)) continue;
    if (vehicle.isValid) setDrilling(vehicle, false);
    else spinning.delete(id);
  }
}

system.runInterval(() => drillTick(system.currentTick), 1);

// After a reload nobody is drilling yet; stop any drill left spinning.
system.runTimeout(() => {
  for (const dimId of DIMENSIONS) {
    for (const vehicle of safe(() => world.getDimension(dimId).getEntities({ type: VEHICLE_ID })) ?? []) {
      setDrilling(vehicle, false);
    }
  }
}, 20);

// --- placing and picking up -----------------------------------------------------------------------

function besideFace(block, face) {
  const off = { Up: [0, 1, 0], Down: [0, -1, 0], North: [0, 0, -1], South: [0, 0, 1], East: [1, 0, 0], West: [-1, 0, 0] };
  const [dx, dy, dz] = off[face] ?? [0, 1, 0];
  const l = block.location;
  return { x: l.x + dx + 0.5, y: l.y + dy, z: l.z + dz + 0.5 };
}

function isCreative(player) {
  return String(safe(() => player.getGameMode()) ?? "").toLowerCase() === "creative";
}

function useOneFromHand(player) {
  if (isCreative(player)) return true;
  const container = player.getComponent("minecraft:inventory")?.container;
  const slot = player.selectedSlotIndex;
  const item = container?.getItem(slot);
  if (item?.typeId !== ITEM_ID) return false;
  if (item.amount > 1) {
    item.amount -= 1;
    container.setItem(slot, item);
  } else {
    container.setItem(slot, undefined);
  }
  return true;
}

/** `clicked` ({ block, face }) when the player clicked a block within reach; else we raycast. */
function place(player, clicked) {
  const now = system.currentTick;
  if (now - (lastUse.get(player.id) ?? -1000) < COOLDOWN_TICKS) return;
  lastUse.set(player.id, now);
  const hit = clicked ?? player.getBlockFromViewDirection({ maxDistance: PLACE_RANGE });
  if (!hit) {
    player.onScreenDisplay.setActionBar("§7Aim at the ground to put the Mooshroom Drill down.");
    return;
  }
  if (!useOneFromHand(player)) return;
  const at = besideFace(hit.block, hit.face);
  let vehicle;
  try {
    vehicle = player.dimension.spawnEntity(VEHICLE_ID, at);
  } catch {
    if (!isCreative(player)) give(player, new ItemStack(ITEM_ID, 1)); // give it back
    return;
  }
  // face away from the player, so they can climb on the back
  safe(() => vehicle.setRotation({ x: 0, y: player.getRotation().y }));
  player.dimension.playSound("random.anvil_land", at, { volume: 0.5, pitch: 1.2 });
  player.dimension.playSound("mob.cow.say", at, { volume: 1.0, pitch: 1.0 });
  player.onScreenDisplay.setActionBar("§eMooshroom Drill! §fUse it to get in, hold forward to dig. Sneak + hit to pick up.");
}

function pickUp(player, vehicle) {
  const at = vehicle.location;
  for (const rider of safe(() => vehicle.getComponent("minecraft:rideable").getRiders()) ?? []) {
    safe(() => vehicle.getComponent("minecraft:rideable").ejectRider(rider));
  }
  spinning.delete(vehicle.id);
  safe(() => vehicle.remove());
  if (!isCreative(player)) give(player, new ItemStack(ITEM_ID, 1));
  player.dimension.playSound("random.pop", at);
}

world.afterEvents.entityHitEntity.subscribe((ev) => {
  const { damagingEntity: by, hitEntity: hit } = ev;
  if (hit?.typeId !== VEHICLE_ID || by?.typeId !== "minecraft:player") return;
  if (by.isSneaking) {
    pickUp(by, hit);
  } else {
    safe(() => hit.dimension.playSound("mob.cow.say", hit.location, { pitch: 1.3 }));
    by.onScreenDisplay.setActionBar("§7The mooshroom doesn't mind. Sneak + hit to pick up the drill.");
  }
});

world.afterEvents.itemUse.subscribe((ev) => {
  if (ev.itemStack?.typeId === ITEM_ID && ev.source?.typeId === "minecraft:player") place(ev.source);
});

// Clicking a block within reach doesn't fire itemUse; use the before-event (like drowned_trap.js)
// and place on the next tick.
world.beforeEvents.playerInteractWithBlock.subscribe((ev) => {
  if (!ev.isFirstEvent || ev.itemStack?.typeId !== ITEM_ID) return;
  ev.cancel = true;
  const { player, block, blockFace } = ev;
  system.run(() => place(player, { block, face: blockFace }));
});

world.afterEvents.playerLeave.subscribe((ev) => lastUse.delete(ev.playerId));
