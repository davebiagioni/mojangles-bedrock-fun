// Net Trap. Hand-written (not generated) - edit freely.
//
// mymod:net_trap is a flat block (blocks/net_trap.json) you place on the ground. The first
// creature that walks onto it is caught: held in place on the net for HOLD_TICKS, then the net
// is used up. Mobs, animals, Big Cats and other players are all caught. The player who placed
// the net can walk over it safely (OWNER_IS_SAFE). Breaking the net frees whatever is in it.
//
// How things are held: mobs get Slowness 255 and are put back on the net whenever they get
// pushed off it. Players get movement and jump input turned off (like the Player Trap Orb).
// Players are always given their controls back: when the hold ends, when the net breaks,
// when they rejoin, and when scripts reload (the flag is a dynamic property on the player).
//
// The step-on trigger is the custom block component "mymod:net_trap", registered below.

import { world, system, InputPermissionCategory, GameMode } from "@minecraft/server";

const NET_ID = "mymod:net_trap";
const OWNER_PREFIX = "bigcat_net_owner_"; // world dynamic property per placed net: placer's id
const PROP_HELD = "bigcat_net_held"; // on a player: their controls are locked by a net

const HOLD_TICKS = 200; // 10 s
const OWNER_IS_SAFE = true;
const SNAP_DISTANCE = 0.2; // put the creature back on the net when it drifts further than this
const PARTICLE_INTERVAL = 8;
const LOCKED = [InputPermissionCategory.Movement, InputPermissionCategory.Jump];

// Never caught: too big to hold, or not creatures at all.
const IMMUNE = new Set([
  "minecraft:ender_dragon",
  "minecraft:wither",
  "minecraft:warden",
  "minecraft:elder_guardian",
  "mymod:laser_dot",
  "mymod:grapple_hook",
]);

/** net key -> { entity, dim, pos, at, until, isPlayer, label, ownerId } */
const caught = new Map();

function safe(fn) {
  try {
    return fn();
  } catch {
    return undefined;
  }
}

function netKey(dimId, p) {
  return `${dimId.replace("minecraft:", "")}_${p.x}_${p.y}_${p.z}`;
}

function label(entity) {
  if (entity.typeId === "minecraft:player") return entity.name;
  if (entity.nameTag) return entity.nameTag;
  const bare = entity.typeId.split(":").pop().replace(/_v\d+$/, "");
  return bare
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function tell(player, text) {
  safe(() => player.onScreenDisplay.setActionBar(text));
}

function canCatch(entity, ownerId) {
  if (!entity?.isValid || IMMUNE.has(entity.typeId)) return false;
  if (entity.typeId === "minecraft:player") {
    if (OWNER_IS_SAFE && entity.id === ownerId) return false;
    return safe(() => entity.getGameMode()) !== GameMode.Spectator; // e.g. inside a Player Trap Orb
  }
  if (!entity.getComponent("minecraft:health")) return false; // items, arrows, XP orbs...
  return !safe(() => entity.matches({ families: ["inanimate"] }));
}

function setControls(player, enabled) {
  for (const cat of LOCKED) safe(() => player.inputPermissions.setPermissionCategory(cat, enabled));
  safe(() => player.setDynamicProperty(PROP_HELD, enabled ? undefined : true));
}

// --------------------------------------------------------------------------- catching

function spring(block, entity) {
  const dim = block.dimension;
  const pos = block.location;
  const key = netKey(dim.id, pos);
  if (caught.has(key)) return; // already holding something
  const ownerId = world.getDynamicProperty(OWNER_PREFIX + key);
  if (!canCatch(entity, ownerId)) return;

  const at = { x: pos.x + 0.5, y: pos.y + 0.0625, z: pos.z + 0.5 };
  const isPlayer = entity.typeId === "minecraft:player";
  const rec = { entity, dim, pos, at, until: system.currentTick + HOLD_TICKS, isPlayer, label: label(entity), ownerId };
  caught.set(key, rec);

  safe(() => entity.clearVelocity());
  safe(() => entity.teleport(at, { keepVelocity: false }));
  if (isPlayer) {
    setControls(entity, false);
    tell(entity, `§cYou're caught in a net! (${HOLD_TICKS / 20}s)`);
  } else {
    safe(() => entity.addEffect("slowness", HOLD_TICKS, { amplifier: 255, showParticles: false }));
  }
  safe(() => dim.playSound("dig.wool", at, { pitch: 0.6 }));
  safe(() => dim.playSound("random.bow", at, { pitch: 0.5, volume: 0.6 }));
  for (let i = 0; i < 8; i++) safe(() => dim.spawnParticle("minecraft:falling_dust_scaffolding_particle", around(rec)));

  const owner = typeof ownerId === "string" ? world.getEntity(ownerId) : undefined;
  if (owner?.isValid && owner.id !== entity.id) tell(owner, `§aYour net caught ${rec.label}!`);
}

/** Let go of whatever the net at `key` holds. used: the net is used up (removed). */
function release(key, used) {
  const rec = caught.get(key);
  if (!rec) return;
  caught.delete(key);
  const { entity, dim, pos } = rec;
  if (entity.isValid) {
    if (rec.isPlayer) {
      setControls(entity, true);
      tell(entity, "§aYou wriggled free of the net.");
    } else {
      safe(() => entity.removeEffect("slowness"));
    }
  }
  // Forget the net only when it's gone: a net that's still standing (the creature despawned or
  // the player left) keeps its owner and stays on the list the backup check scans. onBreak and
  // the backup check clear the record for nets that disappear some other way.
  if (used) world.setDynamicProperty(OWNER_PREFIX + key, undefined);
  if (used && safe(() => dim.getBlock(pos)?.typeId) === NET_ID) {
    safe(() => dim.setBlockType(pos, "minecraft:air"));
    safe(() => dim.playSound("dig.wool", rec.at, { pitch: 1.2 }));
  }
}

function around(rec) {
  const l = rec.entity.isValid ? rec.entity.location : rec.at;
  return { x: l.x + (Math.random() - 0.5) * 1.2, y: l.y + Math.random() * 1.6, z: l.z + (Math.random() - 0.5) * 1.2 };
}

// --------------------------------------------------------------------------- the block component

system.beforeEvents.startup.subscribe((ev) => {
  ev.blockComponentRegistry.registerCustomComponent(NET_ID, {
    onStepOn(e) {
      const { block, entity } = e;
      system.run(() => spring(block, entity));
    },
    onBreak(e) {
      const key = netKey(e.dimension.id, e.block.location);
      system.run(() => {
        release(key, false);
        world.setDynamicProperty(OWNER_PREFIX + key, undefined);
      });
    },
  });
});

// Remember who placed each net, so they can walk over it. The same records are the list of
// placed nets that the backup check below looks at.
world.afterEvents.playerPlaceBlock.subscribe((ev) => {
  if (ev.block.typeId !== NET_ID) return;
  world.setDynamicProperty(OWNER_PREFIX + netKey(ev.dimension.id, ev.block.location), ev.player.id);
});

// Backup for onStepOn, which doesn't reliably fire for mobs on a block this thin: every
// SCAN_INTERVAL ticks, look for creatures standing on each placed net.
const SCAN_INTERVAL = 4;

/** "overworld_10_64_-3" -> { dimId, pos } (the inverse of netKey) */
function parseKey(key) {
  const m = /^(.+)_(-?\d+)_(-?\d+)_(-?\d+)$/.exec(key);
  if (!m) return undefined;
  return { dimId: `minecraft:${m[1]}`, pos: { x: Number(m[2]), y: Number(m[3]), z: Number(m[4]) } };
}

system.runInterval(() => {
  for (const id of world.getDynamicPropertyIds()) {
    if (!id.startsWith(OWNER_PREFIX)) continue;
    const key = id.slice(OWNER_PREFIX.length);
    if (caught.has(key)) continue;
    const net = parseKey(key);
    const dim = net && safe(() => world.getDimension(net.dimId));
    if (!dim) continue;
    const block = safe(() => dim.getBlock(net.pos));
    if (!block) continue; // chunk not loaded
    if (block.typeId !== NET_ID) {
      world.setDynamicProperty(id, undefined); // net broken or replaced while nobody was looking
      continue;
    }
    const { x, y, z } = net.pos;
    const center = { x: x + 0.5, y, z: z + 0.5 };
    const near = safe(() => dim.getEntities({ location: center, maxDistance: 1.5 })) ?? [];
    const onIt = near.find((e) => {
      const l = e.location;
      return l.x >= x && l.x < x + 1 && l.z >= z && l.z < z + 1 && l.y >= y - 0.1 && l.y < y + 0.6 && canCatch(e, world.getDynamicProperty(id));
    });
    if (onIt) spring(block, onIt);
  }
}, SCAN_INTERVAL);

// --------------------------------------------------------------------------- holding

system.runInterval(() => {
  const now = system.currentTick;
  for (const [key, rec] of caught) {
    const netGone = safe(() => rec.dim.getBlock(rec.pos)?.typeId) !== NET_ID;
    if (!rec.entity.isValid || netGone) {
      release(key, false);
      continue;
    }
    if (now >= rec.until) {
      release(key, true);
      continue;
    }
    const l = rec.entity.location;
    if (Math.hypot(l.x - rec.at.x, l.z - rec.at.z) > SNAP_DISTANCE || l.y > rec.at.y + 0.6) {
      safe(() => rec.entity.teleport({ x: rec.at.x, y: rec.at.y, z: rec.at.z }, { keepVelocity: false }));
    }
    if ((rec.until - now) % PARTICLE_INTERVAL === 0) {
      safe(() => rec.dim.spawnParticle("minecraft:falling_dust_top_snow_particle", around(rec)));
    }
  }
}, 1);

// --------------------------------------------------------------------------- never leave a player stuck

function unlockIfStale(player) {
  if (!player.getDynamicProperty(PROP_HELD)) return;
  for (const rec of caught.values()) if (rec.entity.isValid && rec.entity.id === player.id) return;
  setControls(player, true);
}

world.afterEvents.playerSpawn.subscribe((ev) => unlockIfStale(ev.player));
system.run(() => {
  for (const p of world.getAllPlayers()) unlockIfStale(p); // after /reload, holds in memory are gone
});
