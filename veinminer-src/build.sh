#!/bin/bash
# VeinMiner 构建脚本
# 用于 FCL (Fold Craft Launcher) + NeoForge 26.2 环境
# 无需 Gradle/Maven，直接 javac + jar

set -e

# ── 配置 ───────────────────────────────────
MOD_NAME="veinminer"
MOD_VERSION="1.0.0"
MC_VERSION="26.2-NeoForge"
NF_VERSION="26.2.0.7-beta"

# FCL 库目录
BASE="/storage/emulated/0/FCL/.minecraft/libraries"
NF_BASE="$BASE/net/neoforged"

# ── 编译 classpath（从 FCL 的 libraries 目录收集） ──
CP=$(echo \
  "$NF_BASE/minecraft-client-patched/$NF_VERSION/minecraft-client-patched-$NF_VERSION.jar" \
  "$NF_BASE/neoforge/$NF_VERSION/neoforge-$NF_VERSION-universal.jar" \
  "$NF_BASE/bus/8.0.5/bus-8.0.5.jar" \
  "$NF_BASE/mergetool/2.0.7/mergetool-2.0.7-api.jar" \
  "$NF_BASE/fancymodloader/loader/11.0.13/loader-11.0.13.jar" \
  "$BASE/io/netty/netty-buffer/4.2.15.Final/netty-buffer-4.2.15.Final.jar" \
  "$BASE/io/netty/netty-common/4.2.15.Final/netty-common-4.2.15.Final.jar" \
  "$BASE/io/netty/netty-transport/4.2.15.Final/netty-transport-4.2.15.Final.jar" \
  "$BASE/io/netty/netty-resolver/4.2.15.Final/netty-resolver-4.2.15.Final.jar" \
  "$BASE/io/netty/netty-codec-http/4.2.15.Final/netty-codec-http-4.2.15.Final.jar" \
  "$BASE/io/netty/netty-handler/4.2.15.Final/netty-handler-4.2.15.Final.jar" \
  "$BASE/com/mojang/datafixerupper/10.0.21/datafixerupper-10.0.21.jar" \
  "$BASE/com/mojang/brigadier/1.3.10/brigadier-1.3.10.jar" \
  "$BASE/it/unimi/dsi/fastutil/8.5.18/fastutil-8.5.18.jar" \
  "$BASE/org/slf4j/slf4j-api/2.0.17/slf4j-api-2.0.17.jar" \
  "$BASE/org/jspecify/jspecify/1.0.0/jspecify-1.0.0.jar" \
  | tr '\n' ':')

# ── 清理并创建输出目录 ──
rm -rf build/classes
mkdir -p build/classes

# ── 编译 ──
echo "==> 编译源码..."
javac --release 21 -cp "$CP" -d build/classes src/main/java/com/veinminer/*.java
echo "    编译成功 ($(ls build/classes/com/veinminer/*.class | wc -l) 个 class 文件)"

# ── 打包 ──
echo "==> 打包 JAR..."
mkdir -p build/classes/META-INF
cp src/main/resources/META-INF/neoforge.mods.toml build/classes/META-INF/
cd build/classes
jar cf "../../$MOD_NAME-$MOD_VERSION.jar" .
cd ../..
echo "    打包完成: $MOD_NAME-$MOD_VERSION.jar ($(stat -c%s $MOD_NAME-$MOD_VERSION.jar) 字节)"

# ── 部署（可选） ──
MODS_DIR="/storage/emulated/0/FCL/.minecraft/versions/$MC_VERSION/mods"
if [ -d "$MODS_DIR" ]; then
    cp "$MOD_NAME-$MOD_VERSION.jar" "$MODS_DIR/"
    echo "==> 已部署到 $MODS_DIR"
fi

echo "==> 构建完成!"