package com.veinminer;

import com.mojang.blaze3d.platform.InputConstants;
import net.minecraft.client.KeyMapping;
import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.chat.Component;
import net.minecraft.network.codec.ByteBufCodecs;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.Identifier;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.client.event.ClientTickEvent;
import net.neoforged.neoforge.client.event.InputEvent;
import net.neoforged.neoforge.client.event.RegisterKeyMappingsEvent;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.common.extensions.ICommonPacketListener;
import net.neoforged.neoforge.event.level.block.BreakBlockEvent;
import net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent;
import net.neoforged.neoforge.network.handling.IPayloadContext;

import java.util.*;

@Mod(VeinMinerMod.MOD_ID)
public class VeinMinerMod {
    public static final String MOD_ID = "veinminer";

    // ---- Client ----
    private static final KeyMapping.Category CATEGORY = KeyMapping.Category.register(
        Identifier.fromNamespaceAndPath(MOD_ID, "veinminer")
    );
    private static KeyMapping VEIN_MINE_KEY;

    // ---- Server state ----
    private static final Map<Player, Boolean> ENABLED = new WeakHashMap<>();
    private static final Set<Player> CHAINING = Collections.newSetFromMap(new WeakHashMap<>());

    private static final int MAX_BLOCKS = 64;
    private static final BlockPos[] OFFSETS = {
        new BlockPos(1,0,0), new BlockPos(-1,0,0),
        new BlockPos(0,1,0), new BlockPos(0,-1,0),
        new BlockPos(0,0,1), new BlockPos(0,0,-1)
    };

    public VeinMinerMod(IEventBus modBus, Dist dist) {
        modBus.addListener(this::registerPayloads);

        // BreakBlockEvent is a GAME event (NeoForge.EVENT_BUS), not a mod bus event
        NeoForge.EVENT_BUS.addListener(this::onBreakBlock);

        if (dist == Dist.CLIENT) {
            NeoForge.EVENT_BUS.addListener(this::onClientTick);
            NeoForge.EVENT_BUS.addListener(this::onKeyInput);
            NeoForge.EVENT_BUS.addListener(this::onMousePre);
            modBus.addListener(this::registerKeys);
        }
    }

    // ==================== CLIENT ====================

    private void registerKeys(RegisterKeyMappingsEvent event) {
        VEIN_MINE_KEY = new KeyMapping(
            "key.veinminer.veinmine",
            InputConstants.Type.KEYSYM,
            InputConstants.KEY_F12,
            CATEGORY
        );
        event.register(VEIN_MINE_KEY);
    }

    private void onMousePre(InputEvent.MouseButton.Pre event) {
        if (event.getButton() != 1) return;
        if (VEIN_MINE_KEY == null || !VEIN_MINE_KEY.isDown()) return;
        event.setCanceled(true);
    }

    private boolean lastSentActive = false;

    private void onClientTick(ClientTickEvent.Pre event) {
        // Fallback: keep the key listener as primary, but also check here
        // in case the InputEvent.Key does not fire for some reason.
        syncFlagIfChanged();
    }

    private void onKeyInput(InputEvent.Key event) {
        // Fire on every key press/release — way earlier than any tick event.
        // This guarantees the flag reaches the server BEFORE creative-mode
        // instant block breaking.
        syncFlagIfChanged();
    }

    private void syncFlagIfChanged() {
        var mc = Minecraft.getInstance();
        if (mc.player == null || mc.level == null) return;
        if (VEIN_MINE_KEY == null) return;
        if (!(mc.player.connection instanceof ICommonPacketListener listener)) return;

        boolean active = VEIN_MINE_KEY.isDown() && mc.options.keyAttack.isDown();
        if (active != lastSentActive) {
            lastSentActive = active;
            listener.send(new VeinMinePayload(active));
        }
    }

    // ==================== SERVER ====================

    private void registerPayloads(RegisterPayloadHandlersEvent event) {
        event.registrar("1.0.0")
            .playToServer(VeinMinePayload.TYPE, VeinMinePayload.STREAM_CODEC, this::handle);
    }

    private void handle(VeinMinePayload payload, IPayloadContext context) {
        ENABLED.put(context.player(), payload.active());
    }

    private void onBreakBlock(BreakBlockEvent event) {
        Player player = event.getPlayer();
        if (!(player instanceof ServerPlayer sp)) return;
        if (sp.isSpectator()) return;
        if (!ENABLED.getOrDefault(player, false)) return;
        if (CHAINING.contains(player)) return;

        ServerLevel level = (ServerLevel) event.getLevel();
        BlockPos origin = event.getPos();
        BlockState targetState = event.getState();
        Block targetBlock = targetState.getBlock();
        if (targetBlock == Blocks.BEDROCK) return;

        boolean isCreative = sp.isCreative();

        boolean needsCorrectTool = targetState.requiresCorrectToolForDrops();
        ItemStack tool = sp.getMainHandItem();
        boolean hasTool = !tool.isEmpty();
        int maxDurability = hasTool ? tool.getMaxDamage() : 0;
        boolean hasDurability = hasTool && maxDurability > 0;
        int remainingDurability = hasDurability ? maxDurability - tool.getDamageValue() : Integer.MAX_VALUE;

        if (!isCreative && needsCorrectTool && !tool.isCorrectToolForDrops(targetState)) return;
        if (!isCreative && !hasTool && needsCorrectTool) return;

        List<BlockPos> chain = bfs(level, origin, targetBlock, MAX_BLOCKS, isCreative ? false : needsCorrectTool, isCreative ? ItemStack.EMPTY : tool);
        if (chain.isEmpty()) return;

        // Creative mode: no durability, no food cost, just break.
        // Use setBlock directly instead of destroyBlock to avoid recursion
        // (destroyBlock may not work in creative mode anyway).
        if (isCreative) {
            CHAINING.add(player);
            try {
                int broken = 0;
                for (BlockPos bp : chain) {
                    if (broken >= MAX_BLOCKS) break;
                    if (level.getBlockState(bp).getBlock() != targetBlock) continue;
                    level.setBlock(bp, Blocks.AIR.defaultBlockState(), 3);
                    broken++;
                }
            } finally {
                CHAINING.remove(player);
            }
            return;
        }

        // ---- Survival mode ----
        float singleFoodCost = getSingleBlockFoodCost(targetState);

        int playerFood = sp.getFoodData().getFoodLevel();
        float playerSaturation = sp.getFoodData().getSaturationLevel();
        float totalFoodAvailable = playerFood + playerSaturation;

        int maxByDura = hasDurability ? remainingDurability : Integer.MAX_VALUE;
        int maxByFood = (singleFoodCost > 0.001f)
            ? (int)(totalFoodAvailable / singleFoodCost)
            : Integer.MAX_VALUE;

        int maxPossible = Math.min(chain.size(), Math.min(maxByDura, maxByFood));
        if (maxPossible <= 0) {
            sp.sendSystemMessage(Component.literal("§c[VeinMiner] 饱食度不足，无法连锁！"));
            return;
        }

        CHAINING.add(player);
        try {
            int broken = 0;
            float totalFoodSpent = 0;

            for (BlockPos bp : chain) {
                if (broken >= maxPossible) break;
                if (level.getBlockState(bp).getBlock() != targetBlock) continue;

                if (singleFoodCost > 0.001f) {
                    float currentFood = sp.getFoodData().getFoodLevel()
                        + sp.getFoodData().getSaturationLevel();
                    if (currentFood < singleFoodCost) {
                        sp.sendSystemMessage(Component.literal(
                            "§e[VeinMiner] 饱食度耗尽，停止连锁。已挖掘 §6" + broken + " §e个方块。"
                        ));
                        break;
                    }
                }

                boolean success = sp.gameMode.destroyBlock(bp);
                if (success) {
                    broken++;
                    totalFoodSpent += singleFoodCost;
                }

                if (hasDurability && tool.getDamageValue() >= maxDurability) {
                    sp.sendSystemMessage(Component.literal(
                        "§c[VeinMiner] 工具耐久耗尽，停止连锁。已挖掘 §6" + broken + " §e个方块。"
                    ));
                    break;
                }
            }

            if (broken > 0 && totalFoodSpent > 0.001f) {
                int foodCost = (int) Math.ceil(totalFoodSpent);
                int currentFood = sp.getFoodData().getFoodLevel();
                int currentSat = (int) sp.getFoodData().getSaturationLevel();
                int remaining = foodCost;

                int fromSat = Math.min(remaining, currentSat);
                remaining -= fromSat;
                sp.getFoodData().setSaturation(currentSat - fromSat);

                int fromFood = Math.min(remaining, currentFood);
                sp.getFoodData().setFoodLevel(currentFood - fromFood);

                sp.getFoodData().setSaturation(Math.max(0, sp.getFoodData().getSaturationLevel()));
                sp.getFoodData().setFoodLevel(Math.max(0, sp.getFoodData().getFoodLevel()));
            }
        } finally {
            CHAINING.remove(player);
        }
    }

    private static List<BlockPos> bfs(ServerLevel level, BlockPos start, Block targetBlock,
                                       int maxBlocks, boolean needsCorrectTool, ItemStack tool) {
        Set<BlockPos> visited = new HashSet<>();
        Queue<BlockPos> queue = new ArrayDeque<>();
        List<BlockPos> result = new ArrayList<>();

        visited.add(start);

        for (BlockPos off : OFFSETS) {
            BlockPos nb = start.offset(off);
            if (!visited.contains(nb)) {
                visited.add(nb);
                BlockState ns = level.getBlockState(nb);
                if (ns.getBlock() == targetBlock && !ns.isAir()
                    && canMine(ns, needsCorrectTool, tool)) {
                    result.add(nb);
                    queue.add(nb);
                }
            }
        }

        while (!queue.isEmpty() && result.size() < maxBlocks) {
            BlockPos cur = queue.poll();
            for (BlockPos off : OFFSETS) {
                BlockPos nb = cur.offset(off);
                if (visited.add(nb) && result.size() < maxBlocks) {
                    BlockState ns = level.getBlockState(nb);
                    if (ns.getBlock() == targetBlock && !ns.isAir()
                        && canMine(ns, needsCorrectTool, tool)) {
                        result.add(nb);
                        queue.add(nb);
                    }
                }
            }
        }
        return result;
    }

    private static boolean canMine(BlockState state, boolean needsCorrectTool, ItemStack tool) {
        if (!needsCorrectTool) return true;
        return tool.isCorrectToolForDrops(state);
    }

    private static float getSingleBlockFoodCost(BlockState state) {
        float hardness = state.getDestroySpeed(null, null);
        if (hardness <= 0) return 0;
        return hardness * 0.05f;
    }
}

// ==================== NETWORK PACKET ====================

record VeinMinePayload(boolean active) implements CustomPacketPayload {
    static final CustomPacketPayload.Type<VeinMinePayload> TYPE =
        new CustomPacketPayload.Type<>(Identifier.fromNamespaceAndPath(VeinMinerMod.MOD_ID, "veinmine"));

    @Override public Type<VeinMinePayload> type() { return TYPE; }

    static final StreamCodec<RegistryFriendlyByteBuf, VeinMinePayload> STREAM_CODEC = StreamCodec.composite(
        ByteBufCodecs.BOOL, VeinMinePayload::active,
        VeinMinePayload::new
    );
}