"""桌面陪伴小猫咪 —— 真实猫素材完整版。

设计原则：动作一次只做一个，靠"切图"表现，不在照片上叠加多余形变。
只有翻滚（旋转）、走路 / 跳跃（位移）这三种必须的几何变换。

姿态库（12 张同一只猫的真实照片，已抠图）：
坐 / 眯眼 / 蜷睡 / 露肚皮 / 站立 / 击掌 / 洗脸 / 打哈欠 /
母鸡蹲 / 走路 / 兴奋 / 伸懒腰

玩法：
- 摸猫（悬停滑动）→ 眯眼享受冒爱心，摸久了自己翻肚皮求摸
- 单击摸头 → 爱心 + 亲密度 +1；疯狂连点有连击奖励和特殊反应
- 双击 → 无敌风火轮翻浪；拖拽 → 拎起来
- 右键 / 托盘菜单：击掌、散步、洗脸、伸懒腰、打盹、喂小鱼干…
- 没人理会自己洗脸、母鸡蹲、打哈欠、散步、睡觉
- 不定期冒气泡说话（含"人类，你工作辛苦了"，分时段）
- 亲密度：互动涨、有称号等级、升级有庆祝，进度存盘
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

HERE = os.path.dirname(os.path.abspath(__file__))


def _writable(path: str) -> bool:
    """判断目录是否可写（打包后可能被放在 Program Files 等只读位置）。"""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".w_test")
        with open(probe, "w") as f:
            f.write("1")
        os.remove(probe)
        return True
    except Exception:
        return False


if getattr(sys, "frozen", False):
    # 打包成 exe 后：资源在临时解包目录，存档优先放在 exe 同目录（绿色便携），
    # 同目录不可写时退回 %APPDATA%，保证任何位置都能存住亲密度。
    RES_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    _exe_dir = os.path.dirname(sys.executable)
    DATA_DIR = _exe_dir if _writable(_exe_dir) else os.path.join(
        os.environ.get("APPDATA", _exe_dir), "DesktopCat")
    os.makedirs(DATA_DIR, exist_ok=True)
else:
    RES_DIR = HERE
    DATA_DIR = HERE

ASSETS = os.path.join(RES_DIR, "assets")
SAVE_PATH = os.path.join(DATA_DIR, "cat_save.json")
POS_PATH = os.path.join(DATA_DIR, "cat_pos.txt")

W, H = 380, 380
SPRITE = 330
ANCHOR = QPointF(W / 2, H - 16)
HEAD_Y = SPRITE * 0.76

SPRITE_NAMES = ("sit", "bliss", "sleep", "belly", "stand", "paw",
                "groom", "yawn", "loaf", "walk", "alert", "stretch")

# ---------------------------------------------------------------- 亲密度
LEVELS = [
    (0, "初次见面"), (15, "有点眼熟"), (40, "混个脸熟"), (80, "熟悉的小伙伴"),
    (140, "好朋友"), (220, "亲密无间"), (320, "形影不离"),
    (450, "灵魂伴侣"), (620, "命定之猫"),
]


def level_index(v: float) -> int:
    idx = 0
    for i, (th, _) in enumerate(LEVELS):
        if v >= th:
            idx = i
    return idx


# ---------------------------------------------------------------- 台词
BY_HOUR = [
    (6, 11, ["早上好呀，新的一天也要元气满满", "喵~ 早安，记得吃早饭",
             "今天的阳光很适合打盹"]),
    (11, 14, ["中午啦，记得好好吃饭", "吃饱了才有力气摸猫",
              "午后适合晒太阳和摸我"]),
    (14, 18, ["人类，你工作辛苦了", "累了就歇一会儿吧，我陪你",
              "喝口水，然后摸摸我", "工作再忙，也要记得发呆"]),
    (18, 23, ["晚上好，今天过得怎么样？", "辛苦一天啦，抱抱",
              "记得早点休息哦", "喵呜~ 今晚也要开心"]),
    (23, 6, ["这么晚还不睡吗？", "别熬太晚，我会心疼的",
             "我陪你一会儿，然后就去睡觉"]),
]
GENERAL = ["喵~", "喵呜~", "人类，你工作辛苦了", "摸摸我吧，就现在",
           "咕噜咕噜…（蹭蹭你）", "陪陪我嘛", "你今天也很好看",
           "有一条小鱼干想请你吃（并没有）"]
LOVE_LINES = ["和你在一起的每一天都很开心", "你是我的全世界（喵）",
              "今天也超喜欢你", "有你在身边，什么都不怕"]
PET_LINES = ["咕噜咕噜咕噜…", "好舒服呀~", "就是这里，别停",
             "你的手真温暖", "再摸一会儿嘛"]
BELLY_LINES = ["肚子好痒，谢谢你", "世界上最幸福的猫就是我",
               "轻轻一点，再轻一点", "信任你才给你摸肚子哦"]
SLEEP_LINES = ["呼…呼…（梦见小鱼干）", "别吵，本喵在充电", "Zzz…"]
WAKE_LINES = ["喵？我睡着了呢", "被你发现啦", "有什么吩咐，铲屎官"]
ROLL_LINES = ["看我的无敌风火轮！", "转晕了…扶我一下", "翻滚吧，小猫！"]
FRENZY_LINES = ["哇，好多爱心！", "再戳再戳！", "嘿嘿，好痒~",
                "要坏掉啦哈哈哈", "爱心暴雨！"]
HIGHFIVE_LINES = ["击掌！我们心有灵犀", "耶！", "啪！默契满分"]
FEED_LINES = ["谢谢款待，小鱼干最棒了", "唔咪~ 好吃！", "还想再吃一条"]
FEED_COOL = "刚刚才吃过，吃不下了"
GROOM_LINES = ["本喵的颜值全靠自理", "洗洗脸，精神一下"]
WALK_LINES = ["散步有助于身心健康", "巡视领地中…", "这边看看，那边看看"]
LEVELUP_LINE = "我们的感情变深啦！现在是【{}】"


def line_for_now():
    h = time.localtime().tm_hour
    for a, b, lines in BY_HOUR:
        if a <= h < b or (a > b and (h >= a or h < b)):
            return random.choice(lines)
    return random.choice(GENERAL)


# ---------------------------------------------------------------- 气泡
class BubbleWindow(QWidget):
    """独立于猫窗口的对话气泡，不拦截鼠标。"""

    def __init__(self):
        super().__init__(None,
                         Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowFlag(Qt.WindowTransparentForInput, True)
        self.text = ""
        self.alpha = 0.0
        self.fade = 1.0
        self.hold_until = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

    def say(self, text: str, seconds: float = 3.6):
        self.text = text
        fm = QFontMetricsF(QFont("Microsoft YaHei UI", 11))
        rect = fm.boundingRect(QRectF(0, 0, 216, 500),
                               Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                               text)
        self.resize(max(int(rect.width()) + 34, 90), int(rect.height()) + 24)
        self.alpha = 0.0
        self.fade = 1.0
        self.hold_until = time.time() + seconds
        self.show()
        self.raise_()

    def follow(self, cat_pos: QPoint):
        if not self.isVisible():
            return
        screen = self.screen().availableGeometry()
        x = int(cat_pos.x() + W / 2 - self.width() / 2)
        y = int(cat_pos.y() - self.height() - 14)
        x = max(screen.left() + 4, min(x, screen.right() - self.width() - 4))
        self.move(x, max(screen.top() + 4, y))

    def tick(self):
        if not self.isVisible():
            return
        if self.fade > 0:
            self.alpha = min(1.0, self.alpha + 0.12)
            if self.alpha >= 1.0 and time.time() > self.hold_until:
                self.fade = -1.0
        else:
            self.alpha = max(0.0, self.alpha - 0.08)
            if self.alpha <= 0.0:
                self.hide()
        self.update()

    def paintEvent(self, _):
        if self.alpha <= 0 or not self.text:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        a = self.alpha
        bw, bh = self.width(), self.height()
        bubble_h = bh - 12
        path = QPainterPath()
        path.addRoundedRect(QRectF(1, 1, bw - 2, bubble_h), 14, 14)
        cx = bw / 2
        path.moveTo(cx - 9, bubble_h - 2)
        path.lineTo(cx, bubble_h + 11)
        path.lineTo(cx + 9, bubble_h - 2)
        path.closeSubpath()
        p.setPen(QPen(QColor(214, 176, 128, int(210 * a)), 2))
        p.setBrush(QColor(255, 252, 244, int(242 * a)))
        p.drawPath(path)
        p.setPen(QColor(74, 56, 44, int(255 * a)))
        p.setFont(QFont("Microsoft YaHei UI", 11))
        p.drawText(QRectF(16, 10, bw - 32, bubble_h - 16),
                   Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                   self.text)


# ---------------------------------------------------------------- 形状
def heart_path(size: float) -> QPainterPath:
    path = QPainterPath()
    path.moveTo(0, 4)
    path.cubicTo(-8, -3, -5, -10, 0, -5)
    path.cubicTo(5, -10, 8, -3, 0, 4)
    mat = QTransform()
    mat.scale(size / 8.0, size / 8.0)
    return mat.map(path)


def star_path(size: float) -> QPainterPath:
    path = QPainterPath()
    path.moveTo(0, -1)
    path.quadTo(0.18, -0.18, 1, 0)
    path.quadTo(0.18, 0.18, 0, 1)
    path.quadTo(-0.18, 0.18, -1, 0)
    path.quadTo(-0.18, -0.18, 0, -1)
    mat = QTransform()
    mat.scale(size, size)
    return mat.map(path)


# ---------------------------------------------------------------- 猫
class PetWindow(QWidget):
    def __init__(self):
        super().__init__(None,
                         Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.resize(W, H)

        # ---- 贴图（统一 330x330 画布，猫脚底贴画布底）
        self.pix: dict[str, QPixmap] = {}
        self.img: dict[str, QImage] = {}
        for name in SPRITE_NAMES:
            src = QImage(os.path.join(ASSETS, f"{name}.png"))
            scaled = src.scaled(SPRITE, SPRITE,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)
            self.img[name] = scaled
            self.pix[name] = QPixmap.fromImage(scaled)

        # ---- 精灵切换（淡入淡出）
        self.s_from = "sit"
        self.s_to = "sit"
        self.fade = 1.0
        self.fade_step = 0.0

        # ---- 当前唯一动作
        # {"name","t0","dur","x0","dx","dir","segs","said"}
        self.act = None
        self.next_blink = time.time() + random.uniform(2.0, 5.0)
        self.blink_t = None

        # ---- 行为状态
        self.mode = "idle"          # idle | pet | belly | sleep
        self.pet_energy = 0.0
        self._last_pet_pos = None
        self._last_pet_t = 0.0
        self._pet_move = 0.0
        self.last_interact = time.time()
        self.next_chat = time.time() + random.uniform(35, 90)
        self.next_action = time.time() + random.uniform(12, 24)
        self.dragging = False
        self._drag_offset = None
        self._press_pos = QPoint(0, 0)
        self.click_times: list[float] = []
        self.combo = 0

        # ---- 亲密度
        self.save = self._load_save()
        self.hud_alpha = 0.0
        self.hud_hold_until = 0.0

        # ---- 粒子 [kind, x, y, vx, vy, life, size, text]
        self.parts: list[list] = []

        self.bubble = BubbleWindow()
        self.tray = self._make_tray()

        self.loop = QTimer(self)
        self.loop.timeout.connect(self.tick)
        self.loop.start(30)

    # ================================================ 存档
    def _load_save(self) -> dict:
        data = {"intimacy": 0.0, "clicks": 0, "pets": 0, "rolls": 0,
                "feels": 0, "last_feed": 0.0,
                "adopted": time.strftime("%Y-%m-%d")}
        try:
            if os.path.exists(SAVE_PATH):
                with open(SAVE_PATH, encoding="utf-8") as f:
                    loaded = json.load(f)
                data.update({k: loaded.get(k, v) for k, v in data.items()})
        except Exception:
            pass
        return data

    def _write_save(self):
        try:
            with open(SAVE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.save, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def _save_position(self):
        try:
            with open(POS_PATH, "w", encoding="utf-8") as f:
                f.write(f"{self.x()},{self.y()}")
        except OSError:
            pass

    # ================================================ 托盘 / 菜单
    MENU_ITEMS = (
        ("跟你打个招呼", "greet"),
        ("击个掌", "highfive"),
        ("去散步", "walk"),
        ("翻个滚", "roll"),
        ("露个肚皮", "belly"),
        ("伸个懒腰", "stretch"),
        ("洗个脸", "groom"),
        ("打个盹", "sleep"),
        ("喂小鱼干", "feed"),
        ("看看亲密度", "hud"),
        ("回到屏幕内", "home"),
    )

    def _make_tray(self) -> QSystemTrayIcon:
        head = self.img["sit"].copy(0, 0, SPRITE, int(SPRITE * 0.62))
        icon = QIcon(QPixmap.fromImage(head.scaled(
            64, 44, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)))
        menu = QMenu()
        for text, key in self.MENU_ITEMS:
            menu.addAction(text, lambda k=key: self.command(k))
        menu.addSeparator()
        menu.addAction("退出", QApplication.instance().quit)
        tray = QSystemTrayIcon(icon)
        tray.setToolTip("桌面小猫咪")
        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda r: self.say(line_for_now())
            if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        tray.show()
        return tray

    def _menu(self) -> QMenu:
        menu = QMenu()
        for text, key in self.MENU_ITEMS:
            menu.addAction(text, lambda k=key: self.command(k))
        menu.addSeparator()
        menu.addAction("退出", QApplication.instance().quit)
        return menu

    def command(self, key: str):
        if key == "greet":
            self.say(line_for_now())
        elif key == "highfive":
            self.do_highfive()
        elif key == "walk":
            self.do_walk()
        elif key == "roll":
            self.do_roll()
        elif key == "belly":
            self.enter_belly()
        elif key == "stretch":
            self.start_act("stretch", 2.4)
        elif key == "groom":
            self.start_act("groom", 2.8, line=random.choice(GROOM_LINES))
        elif key == "sleep":
            self.go_sleep()
        elif key == "feed":
            self.do_feed()
        elif key == "hud":
            self.show_hud()
        elif key == "home":
            self.go_home()

    def go_home(self):
        g = self.screen().availableGeometry()
        self.move(g.right() - W - 90, g.bottom() - H - 70)

    # ================================================ 亲密度
    def add_intimacy(self, amount: float, show_plus: bool = True):
        before = level_index(self.save["intimacy"])
        self.save["intimacy"] = round(self.save["intimacy"] + amount, 2)
        after = level_index(self.save["intimacy"])
        if show_plus and amount >= 0.4:
            self._spawn("plus", text=f"+{amount:g}")
        self.hud_alpha = 1.0
        self.hud_hold_until = time.time() + 3.2
        if after > before:
            self._level_up(after)
        self._write_save()

    def _level_up(self, idx: int):
        title = LEVELS[idx][1]
        for _ in range(10):
            self._spawn("heart", burst=True)
        for _ in range(6):
            self._spawn("star", burst=True)
        self.say(LEVELUP_LINE.format(title), 4.2)
        if idx >= 4 and not self.busy():
            self.do_highfive(line=None)

    def show_hud(self):
        self.hud_alpha = 1.0
        self.hud_hold_until = time.time() + 5.0

    def hud_text(self) -> tuple[str, float]:
        idx = level_index(self.save["intimacy"])
        title = LEVELS[idx][1]
        cur = self.save["intimacy"]
        lo = LEVELS[idx][0]
        hi = LEVELS[idx + 1][0] if idx + 1 < len(LEVELS) else lo + 1
        frac = max(0.0, min(1.0, (cur - lo) / (hi - lo))) if hi > lo else 1.0
        if idx + 1 >= len(LEVELS):
            return f"❤ {title} · 满级", 1.0
        return f"❤ {title} {cur:.0f}/{hi}", frac

    # ================================================ 精灵与动作
    def set_sprite(self, name: str, ms: int = 260):
        if name == self.s_to and self.fade >= 1.0:
            return
        if self.fade >= 1.0:
            self.s_from = self.s_to
        self.s_to = name
        self.fade = 0.0
        self.fade_step = 1.0 / max(1, ms / 30)

    def busy(self) -> bool:
        return self.act is not None or self.dragging

    def start_act(self, name: str, dur: float, line: str | None = None,
                  force: bool = False):
        """开始一个动作：先打断旧动作，保证同一时刻只有一个。"""
        if self.mode == "sleep" and not force and name != "sit":
            return False
        if (self.act or self.dragging) and not force:
            if self.act and self.act["name"] in ("walk", "roll", "hop"):
                return False
        self.act = {"name": name, "t0": time.time(), "dur": dur}
        self.mode = "idle" if name not in ("sleep",) else self.mode
        self.set_sprite("sit" if name == "look" else name, 260)
        if line:
            self.say(line, 2.6)
        return True

    def do_highfive(self, line=True):
        if self.mode == "sleep":
            return
        if not self.start_act("paw", 1.7, line=random.choice(HIGHFIVE_LINES)
                              if line else None, force=True):
            return
        for _ in range(2):
            self._spawn("star", burst=True)
        self.add_intimacy(1.5)

    def do_walk(self):
        if self.mode == "sleep" or self.dragging:
            return
        if self.act and self.act["name"] in ("walk", "roll", "hop"):
            return
        direction = random.choice((-1, 1))
        self.act = {"name": "walk", "t0": time.time(),
                    "dur": random.uniform(2.4, 4.4), "dir": direction,
                    "x0": self.x(), "speed": random.uniform(58, 82)}
        self.mode = "idle"
        self.set_sprite("walk", 240)
        if random.random() < 0.5:
            self.say(random.choice(WALK_LINES), 2.4)

    def do_roll(self, direction=None):
        if self.mode == "sleep" or self.dragging:
            return
        if self.act and self.act["name"] in ("walk", "roll", "hop"):
            return
        if direction is None:
            direction = random.choice((-1, 1))
        self.save["rolls"] = self.save.get("rolls", 0) + 1
        self.add_intimacy(1.0, show_plus=False)
        self.act = {"name": "roll", "t0": time.time(), "dur": 1.75,
                    "curl": 0.32, "spin": 1.05, "uncurl": 0.38,
                    "dir": direction, "x0": self.x(),
                    "dx": direction * random.randint(110, 170), "said": False}
        self.mode = "idle"
        self.set_sprite("sleep", 220)

    def do_hop(self, dx: float, dur: float = 0.6, chain: int = 0):
        if self.dragging or self.act and self.act["name"] == "roll":
            return
        self.act = {"name": "hop", "t0": time.time(), "dur": dur,
                    "x0": self.x(), "dx": dx, "chain": chain}
        self.mode = "idle"
        self.set_sprite("stand", 180)

    def enter_belly(self):
        if self.mode == "sleep" or self.act and self.act["name"] == "roll":
            return
        self.mode = "belly"
        self.act = None
        self.set_sprite("belly", 300)
        self.say(random.choice(["要摸肚子吗？", "看，软软的"]))

    def do_feed(self):
        now = time.time()
        if now - self.save.get("last_feed", 0) < 60:
            self.say(FEED_COOL, 2.4)
            return
        self.save["last_feed"] = now
        self.save["feels"] = self.save.get("feels", 0) + 1
        self.mode = "idle"
        self.act = {"name": "bliss", "t0": now, "dur": 2.8}
        self.set_sprite("bliss", 220)
        self.say(random.choice(FEED_LINES), 2.8)
        for _ in range(4):
            self._spawn("heart", burst=True)
        self.add_intimacy(3.0, show_plus=False)

    def go_sleep(self):
        if self.act and self.act["name"] in ("walk", "roll", "hop"):
            return
        if self.mode == "sleep":
            return
        # 先打个哈欠，再蜷起来睡（同一个动作，分两段）
        self.mode = "sleep"
        self.act = {"name": "doze", "t0": time.time(), "dur": 1.8}
        self.set_sprite("yawn", 260)

    def wake(self):
        if self.mode != "sleep":
            return
        self.mode = "idle"
        self.pet_energy = 0.0
        self.act = {"name": "stretch", "t0": time.time(), "dur": 2.0}
        self.set_sprite("stretch", 280)
        self.say(random.choice(WAKE_LINES))

    def poke(self):
        self.last_interact = time.time()
        if self.mode == "sleep" and self.act is None:
            self.wake()
        elif self.mode == "sleep" and self.act and self.act["name"] == "doze":
            pass

    def say(self, text: str, seconds: float = 3.6):
        self.bubble.say(text, seconds)
        self.bubble.follow(self.pos())

    # ================================================ 交互
    def hit_test(self, pos: QPoint) -> bool:
        x = int(pos.x() - (ANCHOR.x() - SPRITE / 2))
        y = int(pos.y() - (ANCHOR.y() - SPRITE))
        if not (0 <= x < SPRITE and 0 <= y < SPRITE):
            return False
        return self.img[self.s_to].pixelColor(x, y).alpha() > 50

    def mousePressEvent(self, e):
        self.poke()
        if e.button() == Qt.MouseButton.LeftButton:
            if self.mode == "sleep" and self.act and self.act["name"] == "doze":
                return
            if self.hit_test(e.position().toPoint()):
                self._drag_offset = e.globalPosition().toPoint() - self.pos()
                self._press_pos = e.globalPosition().toPoint()
            else:
                self._drag_offset = None
        elif e.button() == Qt.MouseButton.RightButton:
            self._menu().exec(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        gp = e.globalPosition().toPoint()
        now = time.time()

        if self._drag_offset is not None and e.buttons() & Qt.MouseButton.LeftButton:
            if not self.dragging and (gp - self._press_pos).manhattanLength() > 6:
                self.dragging = True
                self.act = None
                self.mode = "idle"
                self.set_sprite("stand", 200)
            if self.dragging:
                self.move(gp - self._drag_offset)
                self.bubble.follow(self.pos())
            return

        if self.dragging or self.mode == "sleep":
            return
        if not self.hit_test(e.position().toPoint()):
            return
        if self._last_pet_pos is not None and now - self._last_pet_t < 0.4:
            self._pet_move += (gp - self._last_pet_pos).manhattanLength()
        self._last_pet_pos = gp
        self._last_pet_t = now
        if self._pet_move > 44:
            self._pet_move = 0.0
            self.pet_energy += 1.0
            self.last_interact = now
            if self.pet_energy > 1.2:
                self._spawn("heart")
                self.add_intimacy(0.15, show_plus=False)

        if self.pet_energy > 2.2 and self.mode not in ("pet", "belly"):
            self.mode = "pet"
            self.act = None
            self.set_sprite("bliss", 220)
        if (self.mode == "belly" and self.pet_energy > 2.5
                and random.random() < 0.05):
            self.add_intimacy(0.3, show_plus=False)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        was_drag = self.dragging
        self.dragging = False
        self._drag_offset = None
        self._last_pet_pos = None
        if was_drag:
            if self.mode == "idle":
                self.set_sprite("sit", 260)
            return
        if self.mode == "sleep" or not self.hit_test(e.position().toPoint()):
            return
        self._handle_click()

    def _handle_click(self):
        now = time.time()
        self.click_times = [t for t in self.click_times if now - t < 1.4]
        self.click_times.append(now)
        self.combo = len(self.click_times)
        self.pet_energy = min(self.pet_energy + 1.4, 9)
        self.save["clicks"] = self.save.get("clicks", 0) + 1

        gain = 0.5 + min(1.5, 0.12 * self.combo)
        self.add_intimacy(gain)
        self._spawn("heart")

        if self.mode == "belly":
            self.say(random.choice(BELLY_LINES), 2.2)
            self.add_intimacy(0.8, show_plus=False)
            return

        if self.combo >= 10:
            # 疯狂点击：兴奋起来，爱心变多
            self.act = {"name": "frenzy", "t0": now, "dur": 1.5}
            self.mode = "idle"
            self.set_sprite("alert", 140)
            self._spawn("heart")
            if random.random() < 0.6:
                self.say(random.choice(FRENZY_LINES), 2.2)
        elif self.combo >= 4:
            self.act = {"name": "frenzy", "t0": now, "dur": 1.2}
            self.mode = "idle"
            self.set_sprite("alert", 160)
            if random.random() < 0.3:
                self.say(random.choice(FRENZY_LINES), 2.0)
        elif self.combo == 1 and random.random() < 0.14:
            self.do_highfive()
        elif self.combo == 1 and random.random() < 0.2:
            self.say("喵~", 1.6)

    def mouseDoubleClickEvent(self, e):
        if self.hit_test(e.position().toPoint()):
            self.click_times.clear()
            self.do_roll()

    def leaveEvent(self, _):
        self._last_pet_pos = None

    # ================================================ 粒子
    def _spawn(self, kind: str, text: str | None = None, size=None, burst=False):
        if kind == "heart":
            self.parts.append(["heart",
                               ANCHOR.x() + random.uniform(-50, 50),
                               ANCHOR.y() - HEAD_Y + random.uniform(-16, 8),
                               random.uniform(-12, 12), random.uniform(-58, -38),
                               1.0, size or random.uniform(8, 13), None])
        elif kind == "plus":
            self.parts.append(["plus",
                               ANCHOR.x() + random.uniform(-14, 14),
                               ANCHOR.y() - HEAD_Y - 14,
                               random.uniform(-5, 5), -42, 1.0,
                               13, text or "+1"])
        elif kind == "star":
            if burst:
                ang = random.uniform(0, math.tau)
                sp = random.uniform(60, 120)
                self.parts.append(["star",
                                   ANCHOR.x() + random.uniform(-22, 22),
                                   ANCHOR.y() - HEAD_Y * 0.8,
                                   math.cos(ang) * sp, math.sin(ang) * sp - 26,
                                   1.0, random.uniform(5, 9), None])
            else:
                self.parts.append(["star",
                                   ANCHOR.x() + random.uniform(-44, 44),
                                   ANCHOR.y() - HEAD_Y,
                                   random.uniform(-8, 8), random.uniform(-46, -28),
                                   1.0, random.uniform(5, 8), None])
        elif kind == "zzz":
            self.parts.append(["zzz",
                               ANCHOR.x() + random.uniform(24, 52),
                               ANCHOR.y() - HEAD_Y + random.uniform(-8, 8),
                               10, -24, 1.0, random.uniform(10, 14), None])

    def _update_parts(self, dt):
        alive = []
        for part in self.parts:
            kind, x, y, vx, vy, life, size, text = part
            x += vx * dt
            y += vy * dt
            life -= dt * (0.5 if kind in ("heart", "plus") else
                          0.85 if kind == "star" else 0.4)
            if life > 0:
                alive.append([kind, x, y, vx, vy, life, size, text])
        self.parts = alive

    # ================================================ 主循环
    def tick(self):
        now = time.time()
        dt = 0.03

        if self.fade < 1.0 and self.fade_step:
            self.fade = min(1.0, self.fade + self.fade_step)

        # ---- 动作推进（同一个动作内分阶段，不并发）
        if self.act:
            a = self.act
            name, el = a["name"], now - a["t0"]

            if name == "roll":
                total = a["curl"] + a["spin"] + a["uncurl"]
                if el < a["curl"]:
                    pass
                elif el < a["curl"] + a["spin"]:
                    k = (el - a["curl"]) / a["spin"]
                    k = k * k * (3 - 2 * k)
                    self.move(int(a["x0"] + a["dx"] * k), self.y())
                    if not a["said"]:
                        a["said"] = True
                        self.say(random.choice(ROLL_LINES), 2.2)
                elif el >= total:
                    self.move(int(a["x0"] + a["dx"]), self.y())
                    self.act = None
                    self.set_sprite("sit", 280)
                    self._clamp_into_screen()

            elif name == "walk":
                if el >= a["dur"]:
                    self.act = None
                    self.set_sprite("sit", 280)
                else:
                    self.move(int(self.x() + a["dir"] * a["speed"] * dt), self.y())
                    self._clamp_into_screen()

            elif name == "hop":
                if el >= a["dur"]:
                    self.move(int(a["x0"] + a["dx"]), self.y())
                    self._clamp_into_screen()
                    if a.get("chain", 0) > 0 and not self.dragging:
                        d = random.choice((-1, 1)) * random.randint(40, 90)
                        self.do_hop(d, 0.6, a["chain"] - 1)
                    else:
                        self.act = None
                        self.set_sprite("sit", 260)

            elif name == "doze":
                if el >= a["dur"]:
                    self.act = None
                    self.set_sprite("sleep", 420)
                    self.say(random.choice(SLEEP_LINES), 3.0)

            elif el >= a["dur"]:
                self.act = None
                if self.mode in ("idle", "pet", "belly"):
                    self.set_sprite("sit", 300)

        # ---- 眨眼（只在坐姿空闲时）
        if (self.mode == "idle" and self.act is None and not self.dragging
                and self.fade >= 1.0 and self.s_to == "sit"):
            if self.blink_t is None:
                if now > self.next_blink:
                    self.blink_t = now
                    self.set_sprite("bliss", 70)
            elif now - self.blink_t > 0.14:
                self.blink_t = None
                self.next_blink = now + random.uniform(2.4, 6.0)
                self.set_sprite("sit", 90)

        # ---- 撸猫能量衰减
        if self.pet_energy > 0:
            self.pet_energy = max(0.0, self.pet_energy - dt * 0.55)
        if self.mode == "pet" and self.pet_energy < 0.8:
            self.mode = "idle"
            if self.act is None:
                self.set_sprite("sit", 320)
        if self.mode == "pet" and self.pet_energy > 5 and random.random() < 0.03:
            self.say(random.choice(PET_LINES), 2.4)

        # ---- 自主行为（空闲且没有动作时才会触发）
        idle_for = now - self.last_interact
        if (self.mode == "idle" and self.act is None
                and not self.dragging and not self.bubble.isVisible()):
            if idle_for > 150:
                self.go_sleep()
            elif now > self.next_action:
                self._random_idle_action()
                self.next_action = now + random.uniform(11, 22)

        # ---- 不定期说话
        if (now > self.next_chat and not self.bubble.isVisible()
                and not self.act and not self.dragging):
            idx = level_index(self.save["intimacy"])
            pool = GENERAL + (LOVE_LINES if idx >= 4 else [])
            self.say(random.choice(pool) if random.random() < 0.4
                     else line_for_now(), 4.0)
            self.next_chat = now + random.uniform(80, 190)

        if self.mode == "sleep" and random.random() < 0.03:
            self._spawn("zzz")
        if (self.mode in ("pet", "belly") and self.pet_energy > 3.5
                and random.random() < 0.07):
            self._spawn("heart")

        # ---- HUD 淡出
        if self.hud_alpha > 0 and now > self.hud_hold_until:
            self.hud_alpha = max(0.0, self.hud_alpha - dt * 1.2)

        self._update_parts(dt)
        self.update()

    def _random_idle_action(self):
        idx = level_index(self.save["intimacy"])
        table = [
            (3.0, lambda: self.start_act("groom", 2.8,
                                         line=random.choice(GROOM_LINES)
                                         if random.random() < 0.35 else None)),
            (3.0, lambda: self.start_act("loaf", random.uniform(6, 12))),
            (2.4, self.do_walk),
            (1.6, lambda: self.start_act("yawn", 1.8)),
            (1.4, lambda: self.do_hop(
                random.choice((-1, 1)) * random.randint(50, 110), 0.6,
                chain=random.randint(1, 2))),
            (1.0, lambda: self.start_act("stretch", 2.4)),
            (0.8, self.do_roll),
            (0.5 + idx * 0.3, self.do_highfive),
        ]
        total = sum(w for w, _ in table)
        r = random.uniform(0, total)
        for weight, fn in table:
            r -= weight
            if r <= 0:
                fn()
                return

    # ================================================ 绘制
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        sh = QRadialGradient(ANCHOR + QPointF(0, 2), 84)
        sh.setColorAt(0.0, QColor(30, 20, 10, 62))
        sh.setColorAt(1.0, QColor(30, 20, 10, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(sh)
        p.save()
        p.translate(ANCHOR.x(), ANCHOR.y() + 2)
        p.scale(1.0, 0.16)
        p.drawEllipse(QPointF(0, 0), 84, 84)
        p.restore()

        now = time.time()
        angle = 0.0
        scale = 1.0
        dy = 0.0
        face = 1

        if self.act:
            a = self.act
            el = now - a["t0"]
            if a["name"] == "roll":
                if el < a["curl"]:
                    k = el / a["curl"]
                    scale = 1.0 - 0.44 * (k * k * (3 - 2 * k))
                elif el < a["curl"] + a["spin"]:
                    scale = 0.56
                    k = (el - a["curl"]) / a["spin"]
                    angle = 360.0 * (k * k * (3 - 2 * k)) * a["dir"]
                else:
                    k = min(1.0, (el - a["curl"] - a["spin"]) / a["uncurl"])
                    k = k * k * (3 - 2 * k)
                    scale = 0.56 + 0.44 * k
                    angle = 360.0 * a["dir"]
            elif a["name"] == "hop":
                k = min(1.0, el / a["dur"])
                dy = -math.sin(k * math.pi) * 44
                face = 1 if a["dx"] >= 0 else -1
            elif a["name"] == "walk":
                face = -1 if a["dir"] > 0 else 1   # 素材本身朝左
                dy = -abs(math.sin(el * 9.0)) * 2.0

        p.save()
        p.translate(ANCHOR.x(), ANCHOR.y() + dy)

        def draw_sprite(name, opacity):
            pix = self.pix[name]
            p.setOpacity(opacity)
            p.save()
            if angle:
                p.rotate(angle)
            if scale != 1.0:
                p.scale(scale, scale)
            if face < 0:
                p.scale(-1, 1)
            p.drawPixmap(QPointF(-SPRITE / 2, -SPRITE), pix)
            p.restore()
            p.setOpacity(1.0)

        draw_sprite(self.s_from, 1.0)
        if self.fade < 1.0:
            draw_sprite(self.s_to, self.fade)
        p.restore()

        # ---- 粒子
        for kind, x, y, _, _, life, size, text in self.parts:
            if kind == "heart":
                a_ = int(215 * min(1.0, life * 1.4))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(246, 108, 128, a_))
                p.save()
                p.translate(x, y)
                p.drawPath(heart_path(size))
                p.setBrush(QColor(255, 255, 255, int(150 * min(1.0, life * 1.4))))
                p.translate(-size * 0.25, -size * 0.42)
                p.drawPath(heart_path(size * 0.22))
                p.restore()
            elif kind == "star":
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 216, 110, int(230 * life)))
                p.save()
                p.translate(x, y)
                p.rotate((1.0 - life) * 150)
                p.drawPath(star_path(size))
                p.restore()
            elif kind == "plus":
                p.setFont(QFont("Arial", int(size), QFont.Weight.Bold))
                p.setPen(QPen(QColor(90, 60, 30, int(200 * life)), 3))
                p.drawText(QPointF(x + 1.5, y + 1.5), text)
                p.setPen(QColor(255, 214, 92, int(255 * life)))
                p.drawText(QPointF(x, y), text)
            elif kind == "zzz":
                p.setPen(QColor(150, 170, 200, int(220 * life)))
                p.setFont(QFont("Segoe UI", int(size), QFont.Weight.Bold))
                p.drawText(QPointF(x, y), "z")

        if self.hud_alpha > 0.01:
            self._draw_hud(p)

    def _draw_hud(self, p: QPainter):
        a = self.hud_alpha
        text, frac = self.hud_text()
        p.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.DemiBold))
        fm = QFontMetricsF(p.font())
        tw = fm.horizontalAdvance(text)
        bar_w = max(124.0, tw + 26)
        x = W / 2 - bar_w / 2
        y, hh = 8.0, 24.0

        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, bar_w, hh), 12, 12)
        p.setPen(QPen(QColor(255, 244, 224, int(70 * a)), 1))
        p.setBrush(QColor(28, 24, 20, int(170 * a)))
        p.drawPath(path)

        bx, by, bw2, bh2 = x + 8, y + hh - 9, bar_w - 16, 4.5
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, int(40 * a)))
        p.drawRoundedRect(QRectF(bx, by, bw2, bh2), 2.5, 2.5)
        grad = QLinearGradient(bx, 0, bx + bw2, 0)
        grad.setColorAt(0.0, QColor(255, 138, 156))
        grad.setColorAt(1.0, QColor(255, 190, 120))
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(QRectF(bx, by, max(3.0, bw2 * frac), bh2), 2.5, 2.5)

        p.setPen(QColor(255, 240, 224, int(240 * a)))
        p.drawText(QPointF(W / 2 - tw / 2, y + 15.5), text)

    # ================================================ 其他
    def _clamp_into_screen(self):
        g = self.screen().availableGeometry()
        x = max(g.left() + 8, min(self.x(), g.right() - W - 8))
        y = max(g.top() + 8, min(self.y(), g.bottom() - H - 8))
        self.move(x, y)

    def closeEvent(self, e):
        self._save_position()
        self._write_save()
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("桌面小猫咪")
    app.setWindowIcon(QIcon(os.path.join(ASSETS, "sit.png")))

    cat = PetWindow()
    app.aboutToQuit.connect(cat._save_position)

    first_run = not os.path.exists(SAVE_PATH)
    pos = None
    if os.path.exists(POS_PATH):
        try:
            with open(POS_PATH, encoding="utf-8") as f:
                x, y = f.read().strip().split(",")
                pos = QPoint(int(x), int(y))
        except Exception:
            pos = None
    if pos is None:
        g = cat.screen().availableGeometry()
        pos = QPoint(g.right() - W - 110, g.bottom() - H - 70)
    cat.move(pos)
    cat._clamp_into_screen()
    cat.show()

    QTimer.singleShot(1200, lambda: cat.say(
        "你好呀，我是你的桌面小猫！多多关照" if first_run
        else "人类，你工作辛苦了", 4.4))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
