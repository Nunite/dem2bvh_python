from py_goldsrc_demo.parse_demo import parse_demo
from io import BytesIO
import os
import numpy as np
import argparse


def interpolate_angles(times, angles, target_times):
    angles = np.array(angles)

    # 处理角度突变
    for i in range(1, len(angles)):
        diff = angles[i] - angles[i - 1]
        if abs(diff) > 180:
            # 如果角度差超过180度，说明发生了循环
            if diff > 0:
                angles[i:] -= 360
            else:
                angles[i:] += 360

    # 使用线性插值并将结果映射回0-360范围
    return np.interp(target_times, times, angles) % 360


def resample_positions(positions, source_fps, target_fps):
    """改进的重采样函数，特别处理角度通道"""
    if source_fps == target_fps:
        return positions

    pos_array = np.array(positions)
    original_times = np.arange(len(positions)) / source_fps
    target_times = np.arange(0, original_times[-1], 1 / target_fps)

    # 创建结果数组
    resampled = np.zeros((len(target_times), 6))

    # 对位置进行普通线性插值 (前3个通道)
    for i in range(3):
        resampled[:, i] = np.interp(target_times, original_times, pos_array[:, i])

    # 对角度进行特殊插值 (后3个通道)
    for i in range(3, 6):
        resampled[:, i] = interpolate_angles(
            original_times, pos_array[:, i], target_times
        )

    return resampled.tolist()


def analyze_demo(demo_file: str, target_fps: int = 60):
    """分析demo文件中的位置数据并保存为BVH格式"""
    base_name = os.path.splitext(demo_file)[0]
    output_file = f"{base_name}_camera.bvh"

    # 打开并解析demo文件
    with open(demo_file, "rb") as f:
        demo = parse_demo(BytesIO(f.read()))

    positions = []
    source_frame_time = 1.0 / 60  # 默认值

    # 只处理Playback目录
    for directory in demo.directories:
        if directory.name == "Playback":
            if directory.frames > 0:
                source_frame_time = directory.time / directory.frames

            for macro in directory.macros:
                try:
                    if hasattr(macro, "client_data"):
                        pos = macro.client_data.position
                        rot = macro.client_data.rotation
                        positions.append(
                            (-pos.y, pos.z + 16, -pos.x, -rot.roll, -rot.pitch, rot.yaw)
                        )
                except:
                    continue

    # 计算源帧率并重采样
    source_fps = 1.0 / source_frame_time
    if source_fps != target_fps:
        print(f"Resampling from {source_fps:.1f}fps to {target_fps}fps...")
        positions = resample_positions(positions, source_fps, target_fps)

    target_frame_time = 1.0 / target_fps

    # 写入BVH格式文件
    with open(output_file, "w") as out:
        # 写入头部
        out.write("HIERARCHY\n")
        out.write("ROOT MdtCam\n")
        out.write("{\n")
        out.write("\tOFFSET 0.00 0.00 0.00\n")
        out.write(
            "\tCHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation\n"
        )
        out.write("\tEnd Site\n")
        out.write("\t{\n")
        out.write("\t\tOFFSET 0.00 0.00 -1.00\n")
        out.write("\t}\n")
        out.write("}\n")

        # 写入动作数据
        out.write("MOTION\n")
        out.write(f"Frames: {len(positions)}\n")
        out.write(f"Frame Time: {target_frame_time:.6f}\n")

        # 写入每一帧的数据
        for pos in positions:
            out.write(
                f"{pos[0]:.6f} {pos[1]:.6f} {pos[2]:.6f} {pos[3]:.6f} {pos[4]:.6f} {pos[5]:.6f}\n"
            )

    print(f"Camera motion saved to: {output_file}")
    print(f"Total frames: {len(positions)}")
    print(f"Frame time: {target_frame_time:.6f} ({target_fps} fps)")


class CustomHelpFormatter(argparse.HelpFormatter):
    def _format_usage(self, usage, actions, groups, prefix):
        return ""

    def format_help(self):
        help_text = self._root_section.format_help().rstrip()
        return f"""Analyze GoldSrc demo file and convert to BVH

Usage: {self._prog} <demo_file> [-fps fps_value]

Arguments:
  <demo_file>        Path to the demo file (*.dem)
  -fps fps_value     Target FPS (default: 30)

Author: Lws 
Reference project: https://github.com/tpetrina/WebKZ
"""


def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        formatter_class=CustomHelpFormatter,
        usage=argparse.SUPPRESS,
        add_help=False,  # 禁用默认的帮助信息
    )

    # 添加参数说明
    parser.add_argument(
        "demo_file", metavar="<demo_file>", help=argparse.SUPPRESS  # 隐藏参数说明
    )
    parser.add_argument(
        "-fps",
        type=int,
        default=30,
        metavar="fps_value",
        help=argparse.SUPPRESS,  # 隐藏参数说明
    )

    try:
        # 如果没有参数，显示帮助信息
        import sys

        if len(sys.argv) == 1:
            parser.print_help()
            return

        # 解析命令行参数
        args = parser.parse_args()

        # 检查文件是否存在
        if not os.path.exists(args.demo_file):
            print(f"Error: File '{args.demo_file}' not found")
            return

        # 检查文件扩展名
        if not args.demo_file.lower().endswith(".dem"):
            print("Warning: File does not have .dem extension")

        # 分析demo文件
        analyze_demo(args.demo_file, args.fps)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return


if __name__ == "__main__":
    main()
