import numpy as np


def _neighbor_values(img: np.ndarray) -> tuple[np.ndarray, ...]:
    p2 = img[:-2, 1:-1]
    p3 = img[:-2, 2:]
    p4 = img[1:-1, 2:]
    p5 = img[2:, 2:]
    p6 = img[2:, 1:-1]
    p7 = img[2:, :-2]
    p8 = img[1:-1, :-2]
    p9 = img[:-2, :-2]
    return p2, p3, p4, p5, p6, p7, p8, p9


def zhang_suen_thinning(mask: np.ndarray) -> np.ndarray:
    img = mask.astype(np.uint8).copy()
    if img.shape[0] < 3 or img.shape[1] < 3:
        return img.astype(bool)

    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            padded = np.pad(img, 1, mode="constant")
            p2, p3, p4, p5, p6, p7, p8, p9 = _neighbor_values(padded)
            neighbors = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            transitions = (
                ((p2 == 0) & (p3 == 1)).astype(np.uint8)
                + ((p3 == 0) & (p4 == 1)).astype(np.uint8)
                + ((p4 == 0) & (p5 == 1)).astype(np.uint8)
                + ((p5 == 0) & (p6 == 1)).astype(np.uint8)
                + ((p6 == 0) & (p7 == 1)).astype(np.uint8)
                + ((p7 == 0) & (p8 == 1)).astype(np.uint8)
                + ((p8 == 0) & (p9 == 1)).astype(np.uint8)
                + ((p9 == 0) & (p2 == 1)).astype(np.uint8)
            )
            core = padded[1:-1, 1:-1] == 1
            common = core & (neighbors >= 2) & (neighbors <= 6) & (transitions == 1)
            if step == 0:
                cond = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                cond = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            delete = common & cond
            if np.any(delete):
                img[delete] = 0
                changed = True
    return img.astype(bool)

def recover_T_junctions(mask: np.ndarray, skeleton: np.ndarray) -> np.ndarray:
    """
    针对被Zhang-Suen误删的T字型交点进行回填。
    :param mask: 原始二值掩码（True为前景/黑色）
    :param skeleton: 骨架化结果
    :return: 回填T型交点后的骨架
    """
    diff = (mask.astype(bool)) & (~skeleton)
    result = skeleton.copy()

    # 获取所有被删掉的前景点索引
    coords = np.argwhere(diff)
    # 处理边界
    h, w = mask.shape
    for y, x in coords:
        if not (1 <= y < h - 1 and 1 <= x < w - 1):
            continue  # 跳过边界点
        # 正交邻居坐标
        neighbors = [
            (y-1, x),  # 上
            (y+1, x),  # 下
            (y, x-1),  # 左
            (y, x+1),  # 右
        ]
        cnt = sum([result[yy, xx] for yy, xx in neighbors])
        if cnt == 3:
            result[y, x] = True  # 回填
    return result

def fix_cross_alignment(skeleton: np.ndarray) -> np.ndarray:
    """
    修正十字交叉处的竖线错位。
    只对齐真正的竖线（至少2个像素），忽略孤立点。
    """
    result = skeleton.copy().astype(bool)
    h, w = result.shape
    
    for y in range(1, h - 2):
        for x in range(1, w - 2):
            if not result[y, x]:
                continue
            
            # 检查是否是水平线的一部分
            if not (result[y, x-1] and result[y, x+1]):
                continue
            
            # 检查水平线是否够长
            left_count = 0
            nx = x - 1
            while nx >= 0 and result[y, nx]:
                left_count += 1
                nx -= 1
            
            right_count = 0
            nx = x + 1
            while nx < w and result[y, nx]:
                right_count += 1
                nx += 1
            
            if left_count + right_count + 1 < 3:
                continue
            
            # ==========================================
            # 检查上方竖线
            # ==========================================
            top_x = None
            # 先检查正上方
            if y > 0 and result[y-1, x]:
                # 确认是真正的竖线：再上面还有像素
                if y - 1 > 0 and result[y-2, x]:
                    top_x = x
                else:
                    # 只有1个像素，不算竖线
                    top_x = None
            
            # 如果正上方没有，检查偏移列
            if top_x is None:
                for offset in [-1, 1]:
                    nx = x + offset
                    if 0 <= nx < w and y > 0 and result[y-1, nx]:
                        # 确认是真正的竖线：再上面还有像素
                        if y - 1 > 0 and result[y-2, nx]:
                            top_x = nx
                            break
            
            # ==========================================
            # 检查下方竖线（必须是真正的竖线）
            # ==========================================
            bottom_x = None
            # 先检查正下方
            if y + 1 < h and result[y+1, x]:
                # 确认是真正的竖线：再下面还有像素
                if y + 2 < h and result[y+2, x]:
                    bottom_x = x
                else:
                    # 只有1个像素，不算竖线
                    bottom_x = None
            
            # 如果正下方没有，检查偏移列
            if bottom_x is None:
                for offset in [-1, 1]:
                    nx = x + offset
                    if 0 <= nx < w and y + 1 < h and result[y+1, nx]:
                        # 确认是真正的竖线：再下面还有像素
                        if y + 2 < h and result[y+2, nx]:
                            bottom_x = nx
                            break
            
            # ==========================================
            # 如果上下都是真正的竖线，且错位，则修正
            # ==========================================
            if top_x is not None and bottom_x is not None:
                if top_x != bottom_x and abs(top_x - bottom_x) == 1:
                    # 只移动连接处的1个像素
                    if top_x != x:
                        if y - 1 >= 0 and result[y-1, top_x]:
                            result[y-1, x] = True
                            result[y-1, top_x] = False
                            
                    if bottom_x != x:
                        if y + 1 < h and result[y+1, bottom_x]:
                            result[y+1, x] = True
                            result[y+1, bottom_x] = False
                            
    return result

def remove_redundant_cross_points(skeleton: np.ndarray) -> np.ndarray:
    """
    找到十字交叉中心点，删除其非正交邻居。
    """
    result = skeleton.copy().astype(bool)
    h, w = result.shape
    
    removed = 0
    
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if not result[y, x]:
                continue
            
            # 检查正交方向（上下左右）
            up = result[y-1, x]
            down = result[y+1, x]
            left = result[y, x-1]
            right = result[y, x+1]
            
            orthogonal_count = (1 if up else 0) + (1 if down else 0) + (1 if left else 0) + (1 if right else 0)
            
            # 必须是十字交叉中心：至少3个正交邻居
            if orthogonal_count < 3:
                continue
            
            # 检查四个对角方向，有就删掉
            diagonals = [
                (y-1, x-1),  # 左上
                (y-1, x+1),  # 右上
                (y+1, x-1),  # 左下
                (y+1, x+1),  # 右下
            ]
            
            for ny, nx in diagonals:
                if 0 <= ny < h and 0 <= nx < w and result[ny, nx]:
                    # 这个对角像素就是多余的点，删掉它
                    result[ny, nx] = False
                    removed += 1
                    
    
    return result

