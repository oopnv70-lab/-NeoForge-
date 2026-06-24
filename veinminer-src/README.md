VeinMiner - 连锁挖矿模组
=========================
NeoForge 26.2 (Minecraft 1.21.x)

功能
----
按住 F12 + 左键破坏方块时，自动连锁挖掘周围同类型方块（BFS 6方向搜索，最多64格）。

- 生存模式：计算饱食度和工具耐久消耗，两者用尽时自动停止并提示
- 创造模式：直接移除方块，无消耗，不触发递归事件
- 旁观模式：不触发
- 支持精准采集（工具检查 through isCorrectToolForDrops）
- 基岩不会被连锁

文件结构
--------
veinminer-src/
├── build.sh                        # 构建脚本
├── README.md                       # 本文件
└── src/
    ├── main/
    │   ├── java/com/veinminer/
    │   │   └── VeinMinerMod.java   # 主模组代码
    │   └── resources/META-INF/
    │       └── neoforge.mods.toml  # 模组元数据
    └── (仅此而已，无第三方依赖)

构建
----
需求：
- JDK 21+
- Android 终端（Termux/FCL 内置终端）
- FCL 已安装 NeoForge 26.2

步骤：
    chmod +x build.sh
    ./build.sh

产物：veinminer-1.0.0.jar

当 NeoForge 版本升级后，需更新 build.sh 中的：
- NF_VERSION（NeoForge 版本号）
- 各依赖 jar 的版本号（bus, netty, fastutil, datafixerupper, fml loader 等）
  可通过 find /storage/emulated/0/FCL/.minecraft/libraries -name '*.jar' 查找实际版本

部署
----
将 veinminer-1.0.0.jar 复制到 FCL 版本的 mods 目录：
    /storage/emulated/0/FCL/.minecraft/versions/26.2-NeoForge/mods/

技术细节
--------
- 纯 API 调用，无 Mixin/ASM/反射/游戏源码修改
- 使用 NeoForge.EVENT_BUS（非 mod bus）注册 BreakBlockEvent
- 客户端按键通过 InputEvent.Key + ClientTickEvent.Pre 双保险同步到服务端
- 网络包：CustomPacketPayload + StreamCodec（ByteBufCodecs.BOOL）
- 创造模式用 level.setBlock 绕过递归；生存模式用 sp.gameMode.destroyBlock

许可
----
MIT