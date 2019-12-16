# Copyright 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
from platform import system
from os import makedirs
from os.path import basename, isdir, join

from SCons.Script import (ARGUMENTS, COMMAND_LINE_TARGETS, AlwaysBuild,
                          Builder, Default, DefaultEnvironment)


env = DefaultEnvironment()
platform = env.PioPlatform()
board = env.BoardConfig()

env.Replace(
    AR="arm-none-eabi-ar",
    AS="arm-none-eabi-as",
    CC="arm-none-eabi-gcc",
    CXX="arm-none-eabi-g++",
    GDB="arm-none-eabi-gdb",
    OBJCOPY="arm-none-eabi-objcopy",
    RANLIB="arm-none-eabi-ranlib",
    SIZETOOL="arm-none-eabi-size",

    CAT="cat",

    ARFLAGS=["rc"],

    SIZEPROGREGEXP=r"^(?:\.text|\.data|\.rodata|\.text.align|\.ARM.exidx)\s+(\d+).*",
    SIZEDATAREGEXP=r"^(?:\.data|\.bss|\.noinit)\s+(\d+).*",
    SIZECHECKCMD="$SIZETOOL -A -d $SOURCES",
    SIZEPRINTCMD='$SIZETOOL -B -d $SOURCES',

    PROGSUFFIX=".elf"
)

# Allow user to override via pre:script
if env.get("PROGNAME", "program") == "program":
    env.Replace(PROGNAME="firmware")

def combine_hex(source, target, env):
    # cat source[0] source[1] > target[0]’
    print(source[0])
    print(source[1])
    print(target[0])
    print("$CAT " + str(source[0]) + " " + str(source[1]) + " > " + str(target[0]))
    env.Execute("$CAT " + str(source[0]) + " " + str(source[1]) + " > " + str(target[0]))
    return 0


env.Append(
    BUILDERS=dict(
        ElfToBin=Builder(
            action=env.VerboseAction(" ".join([
                "$OBJCOPY",
                "-O",
                "binary",
                "$SOURCES",
                "$TARGET"
            ]), "Building $TARGET"),
            suffix=".bin"
        ),
        ElfToHex=Builder(
            action=env.VerboseAction(" ".join([
                "$OBJCOPY",
                "-O",
                "ihex",
                "-R",
                ".eeprom",
                "$SOURCES",
                "$TARGET"
            ]), "Building $TARGET"),
            suffix=".hex"
        ),
        KernelElfToHex=Builder(
            action=env.VerboseAction(" ".join([
                "$OBJCOPY",
                "$SOURCES",
                "-O",
                "ihex",
                "$TARGET"
            ]), "Building $TARGET"),
            suffix=".hex"
        ),
        HexToElf=Builder(
            action=env.VerboseAction(" ".join([
                "$OBJCOPY",
                "-I",
                "ihex",
                "$SOURCES",
                "-O",
                "elf32-littlearm",
                "$TARGET"
            ]), "Converting hex to elf $TARGET"),
            suffix=".elf"
        ),
        CombineHex=Builder(
            action= combine_hex,
            suffix=".hex"
        )
    )
)

if not env.get("PIOFRAMEWORK"):
    env.SConscript("frameworks/_bare.py")

#
# Target: Build executable and linkable firmware
#

if "zephyr" in env.get("PIOFRAMEWORK", []):
    env.SConscript(
        join(platform.get_package_dir(
            "framework-zephyr"), "scripts", "platformio", "platformio-build-pre.py"),
        exports={"env": env}
    )

target_elf = None
if "nobuild" in COMMAND_LINE_TARGETS:
    target_elf = join("$BUILD_DIR", "${PROGNAME}.elf")
    target_firm = join("$BUILD_DIR", "${PROGNAME}.bin")
elif "detox" in env.get("PIOFRAMEWORK", []):
    # env.SConscript(
    #         join(platform.get_package_dir(
    #             "framework-detox"), "platformio", "platformio-build-post.py"),
    #         exports={"env": env}
    #     )
    print("******** GOT HERE ***********")
    target_elf = env.BuildProgram()

    target_hex = env.ElfToHex(join("$BUILD_DIR", "${PROGNAME}"), target_elf)
    kernel_hex = env.KernelElfToHex(join("$BUILD_DIR", "detox-kernel"), join(platform.get_package_dir("framework-detox"), "detox-kernel", "detox-kernel.elf"))

    # print(target_hex)
    # print(kernel_hex)
    # print(type(kernel_hex))
    combined_hex = env.CombineHex(join("$BUILD_DIR", "combined"), [kernel_hex, target_hex])
    # print("cat " + kernel_hex[0] + " " + target_hex[0] + " > " + "combined.hex")
    # env.Execute("cat " + kernel_hex + " " + target_hex + " > " + join("$BUILD_DIR", "combined.hex"))
    
    # env.Command(join("$BUILD_DIR", "combined.hex"), target_hex, "cat $SOURCE > $TARGET")

    print("** BEFORE COMBINE **")
    print("$CAT " + str(kernel_hex) + " " + str(target_hex) + " > " + "combine.hex")
    combined_elf = env.HexToElf(join("$BUILD_DIR", "combined"), join("$BUILD_DIR", "combined.hex"))


    # target_hex = env.ElfToHex(join("$BUILD_DIR", "${PROGNAME}"), target_elf)
    target_firm = env.ElfToBin(join("$BUILD_DIR", "${PROGNAME}"), combined_elf)
# else:
#     target_elf = env.BuildProgram()
#     target_firm = env.ElfToBin(join("$BUILD_DIR", "${PROGNAME}"), target_elf)

AlwaysBuild(env.Alias("nobuild", target_firm))
target_buildprog = env.Alias("buildprog", target_firm, target_firm)

#
# Target: Print binary size
#

target_size = env.Alias(
    "size", target_elf,
    env.VerboseAction("$SIZEPRINTCMD", "Calculating size $SOURCE"))
AlwaysBuild(target_size)

#
# Target: Upload by default .bin file
#

upload_protocol = env.subst("$UPLOAD_PROTOCOL")
debug_tools = board.get("debug.tools", {})
upload_source = target_firm
upload_actions = []

if upload_protocol == "mbed":
    upload_actions = [
        env.VerboseAction(env.AutodetectUploadPort, "Looking for upload disk..."),
        env.VerboseAction(env.UploadToDisk, "Uploading $SOURCE")
    ]

elif upload_protocol.startswith("blackmagic"):
    env.Replace(
        UPLOADER="$GDB",
        UPLOADERFLAGS=[
            "-nx",
            "--batch",
            "-ex", "target extended-remote $UPLOAD_PORT",
            "-ex", "monitor %s_scan" %
            ("jtag" if upload_protocol == "blackmagic-jtag" else "swdp"),
            "-ex", "attach 1",
            "-ex", "load",
            "-ex", "compare-sections",
            "-ex", "kill"
        ],
        UPLOADCMD="$UPLOADER $UPLOADERFLAGS $SOURCE"
    )
    upload_source = target_elf
    upload_actions = [
        env.VerboseAction(env.AutodetectUploadPort, "Looking for BlackMagic port..."),
        env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")
    ]

elif upload_protocol.startswith("jlink"):

    def _jlink_cmd_script(env, source):
        build_dir = env.subst("$BUILD_DIR")
        if not isdir(build_dir):
            makedirs(build_dir)
        script_path = join(build_dir, "upload.jlink")
        commands = [
            "h",
            "loadbin %s, %s" % (source, board.get(
                "upload.offset_address", "0x08000000")),
            "r",
            "q"
        ]
        with open(script_path, "w") as fp:
            fp.write("\n".join(commands))
        return script_path

    env.Replace(
        __jlink_cmd_script=_jlink_cmd_script,
        UPLOADER="JLink.exe" if system() == "Windows" else "JLinkExe",
        UPLOADERFLAGS=[
            "-device", board.get("debug", {}).get("jlink_device"),
            "-speed", "4000",
            "-if", ("jtag" if upload_protocol == "jlink-jtag" else "swd"),
            "-autoconnect", "1"
        ],
        UPLOADCMD='$UPLOADER $UPLOADERFLAGS -CommanderScript "${__jlink_cmd_script(__env__, SOURCE)}"'
    )
    upload_actions = [env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")]


elif upload_protocol == "dfu":
    hwids = board.get("build.hwids", [["0x0483", "0xDF11"]])
    vid = hwids[0][0]
    pid = hwids[0][1]

    # default tool for all boards with embedded DFU bootloader over USB
    _upload_tool = "dfu-util"
    _upload_flags = [
        "-d", "vid:pid,%s:%s" % (vid, pid),
        "-a", "0", "-s",
        "%s:leave" % board.get("upload.offset_address", "0x08000000"), "-D"
    ]

    upload_actions = [env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")]

    if board.get("build.mcu").startswith("stm32f103") and "arduino" in env.get(
        "PIOFRAMEWORK"):
        # F103 series doesn't have embedded DFU over USB
        # stm32duino bootloader (v1, v2) is used instead
        def __configure_upload_port(env):
            return basename(env.subst("$UPLOAD_PORT"))

        _upload_tool = "maple_upload"
        _upload_flags = [
            "${__configure_upload_port(__env__)}",
            board.get("upload.boot_version", 2),
            "%s:%s" % (vid[2:], pid[2:])
        ]

        env.Replace(__configure_upload_port=__configure_upload_port)

        upload_actions.insert(
            0, env.VerboseAction(env.AutodetectUploadPort,
                                 "Looking for upload port..."))

    if _upload_tool == "dfu-util":
        # Add special DFU header to the binary image
        env.AddPostAction(
            join("$BUILD_DIR", "${PROGNAME}.bin"),
            env.VerboseAction(
                " ".join([
                    join(platform.get_package_dir("tool-dfuutil") or "",
                         "bin", "dfu-suffix"),
                    "-v %s" % vid,
                    "-p %s" % pid,
                    "-d 0xffff", "-a", "$TARGET"
                ]), "Adding dfu suffix to ${PROGNAME}.bin"))

    env.Replace(
        UPLOADER=_upload_tool,
        UPLOADERFLAGS=_upload_flags,
        UPLOADCMD='$UPLOADER $UPLOADERFLAGS "${SOURCE.get_abspath()}"')

    upload_source = target_firm

elif upload_protocol == "serial":
    def __configure_upload_port(env):
        return env.subst("$UPLOAD_PORT")

    env.Replace(
        __configure_upload_port=__configure_upload_port,
        UPLOADER=join(
            platform.get_package_dir("tool-stm32duino") or "",
            "stm32flash", "stm32flash"),
        UPLOADERFLAGS=[
            "-g", board.get("upload.offset_address", "0x08000000"),
            "-b", "115200", "-w"
        ],
        UPLOADCMD='$UPLOADER $UPLOADERFLAGS "$SOURCE" "${__configure_upload_port(__env__)}"'
    )

    upload_actions = [
        env.VerboseAction(env.AutodetectUploadPort, "Looking for upload port..."),
        env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")
    ]

elif upload_protocol == "hid":
    def __configure_upload_port(env):
        return basename(env.subst("$UPLOAD_PORT"))

    env.Replace(
        __configure_upload_port=__configure_upload_port,
        UPLOADER="hid-flash",
        UPLOADCMD='$UPLOADER "$SOURCES" "${__configure_upload_port(__env__)}"'
    )
    upload_actions = [
        env.VerboseAction(env.AutodetectUploadPort, "Looking for upload port..."),
        env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")
    ]

elif upload_protocol in debug_tools:
    openocd_args = [
        "-d%d" % (2 if int(ARGUMENTS.get("PIOVERBOSE", 0)) else 1)
    ]
    openocd_args.extend(
        debug_tools.get(upload_protocol).get("server").get("arguments", []))
    openocd_args.extend([
        "-c", "program {$SOURCE} %s verify reset; shutdown;" %
        board.get("upload.offset_address", "")
    ])
    openocd_args = [
        f.replace("$PACKAGE_DIR",
                  platform.get_package_dir("tool-openocd") or "")
        for f in openocd_args
    ]
    env.Replace(
        UPLOADER="openocd",
        UPLOADERFLAGS=openocd_args,
        UPLOADCMD="$UPLOADER $UPLOADERFLAGS")

    if not board.get("upload").get("offset_address"):
        upload_source = target_elf
    upload_actions = [env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")]

# custom upload tool
elif upload_protocol == "custom":
    upload_actions = [env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")]

else:
    sys.stderr.write("Warning! Unknown upload protocol %s\n" % upload_protocol)

AlwaysBuild(env.Alias("upload", upload_source, upload_actions))

#
# Default targets
#

Default([target_buildprog, target_size])
