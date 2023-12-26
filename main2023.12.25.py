# -*- coding: utf-8 -*-
# Created by: Raf
# Modify by: Vincentzyx

import GameHelper as gh
from GameHelper import GameHelper
import os
import sys
import signal
import time
import DetermineColor as DC
from collections import defaultdict
from douzero.env.move_detector import get_move_type
import cv2
import numpy as np
import pygame
from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import QTime, QEventLoop, Qt, QFile, QTextStream
from MainWindow import Ui_Form

from douzero.env.game import GameEnv
from douzero.evaluation.deep_agent import DeepAgent
import traceback
from skimage.metrics import structural_similarity as ssim

from cnocr import CnOcr

ocr = CnOcr(det_model_name='en_PP-OCRv3_det', rec_model_name='en_PP-OCRv3',
            cand_alphabet="12345678910")  # 所有参数都使用默认值

import BidModel
import LandlordModel
import FarmerModel

EnvCard2RealCard = {3: '3', 4: '4', 5: '5', 6: '6', 7: '7',
                    8: '8', 9: '9', 10: 'T', 11: 'J', 12: 'Q',
                    13: 'K', 14: 'A', 17: '2', 20: 'X', 30: 'D'}

RealCard2EnvCard = {'3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
                    '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12,
                    'K': 13, 'A': 14, '2': 17, 'X': 20, 'D': 30}

AllEnvCard = [3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6, 7, 7, 7, 7,
              8, 8, 8, 8, 9, 9, 9, 9, 10, 10, 10, 10, 11, 11, 11, 11, 12,
              12, 12, 12, 13, 13, 13, 13, 14, 14, 14, 14, 17, 17, 17, 17, 20, 30]

AllCards = ['D', 'X', '2', 'A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3']

helper = GameHelper()


def get_ocr_fast():
    pos = (1050, 756, 120, 40)
    img, _ = helper.Screenshot()
    img = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
    gray_img = cv2.cvtColor(np.asarray(img), cv2.COLOR_BGR2GRAY)
    _, binary_image = cv2.threshold(gray_img, 128, 255, cv2.THRESH_BINARY)
    img = img[pos[1]:pos[1] + pos[3], pos[0]:pos[0] + pos[2]]
    result = ocr.ocr(img)
    if len(result) > 0:
        result = result[0]['text']
        beishu = int(result)
    else:
        beishu = 30
    return beishu


def get_ocr_cards(pos):
    img, _ = helper.Screenshot()
    img = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
    gray_img = cv2.cvtColor(np.asarray(img), cv2.COLOR_BGR2GRAY)
    _, binary_image = cv2.threshold(gray_img, 128, 255, cv2.THRESH_BINARY)
    img = img[pos[1]:pos[1] + pos[3], pos[0]:pos[0] + pos[2]]
    result = ocr.ocr(img)
    if len(result) > 0:
        result = result[0]['text']
        cards_num = int(result)
    else:
        cards_num = 0
    return cards_num


def play_sound(sound_file):
    pygame.mixer.init()
    pygame.mixer.music.load(sound_file)
    pygame.mixer.music.play()


class MyPyQT_Form(QtWidgets.QWidget, Ui_Form):
    def __init__(self):
        super(MyPyQT_Form, self).__init__()
        self.firt_time = 0
        self.my_pass_sign = None
        self.my_played_cards_env = None
        self.my_played_cards_real = None
        self.auto_sign = None
        self.winrate = None
        self.in_game_flag = None
        self.initial_mingpai = None
        self.initial_multiply = None
        self.buy_chaojijiabei_flag = None
        self.initial_cards = None
        self.RunGame = None
        self.initial_bid_rate = None
        self.initial_model_rate = None
        self.other_hands_cards_str = None
        self.stop_sign = None
        self.loop_sign = None
        self.env = None
        self.three_landlord_cards_env = None
        self.three_landlord_cards_real = None
        self.user_hand_cards_env = None
        self.user_hand_cards_real = None
        self.play_order = None
        self.card_play_data_list = None
        self.other_hand_cards = None
        self.other_played_cards_env = None
        self.other_played_cards_real = None
        self.user_position = None
        self.user_position_code = None
        self.setupUi(self)
        self.setWindowFlags(QtCore.Qt.WindowMinimizeButtonHint |  # 使能最小化按钮
                            QtCore.Qt.WindowStaysOnTopHint |  # 窗体总在最前端
                            QtCore.Qt.WindowCloseButtonHint)
        self.setWindowIcon(QIcon(':/pics/favicon.ico'))
        self.setWindowTitle("DouZero欢乐斗地主v4.4")
        self.setFixedSize(self.width(), self.height())  # 固定窗体大小
        self.move(20, 20)
        window_pale = QtGui.QPalette()

        self.setPalette(window_pale)
        self.HandButton.clicked.connect(self.hand_game)
        self.AutoButton.clicked.connect(self.auto_game)
        self.StopButton.clicked.connect(self.stop)

        # self.Players = [self.RPlayer, self.Player, self.LPlayer]
        self.Players = [self.RPlayedCard, self.PredictedCard, self.LPlayedCard]
        self.counter = QTime()

        # 参数
        self.MyConfidence = 0.8  # 我的牌的置信度
        self.OtherConfidence = 0.8  # 别人的牌的置信度
        self.WhiteConfidence = 0.85  # 检测白块的置信度
        self.LandlordFlagConfidence = 0.8  # 检测地主标志的置信度
        self.ThreeLandlordCardsConfidence = 0.8  # 检测地主底牌的置信度
        self.PassConfidence = 0.7

        self.PassConfidence = 0.8
        self.WaitTime = 1  # 等待状态稳定延时
        self.MyFilter = 40  # 我的牌检测结果过滤参数
        self.OtherFilter = 25  # 别人的牌检测结果过滤参数
        self.SleepTime = 0.1  # 循环中睡眠时间
        # ------ 阈值 ------
        self.BidThresholds = [0.3,  # 叫地主阈值
                              0.4,  # 抢地主阈值 (自己第一个叫地主)
                              0.5]  # 抢地主阈值 (自己非第一个叫地主)
        self.JiabeiThreshold = (
            (0.75, 0.5),  # 超级加倍 加倍 阈值
            (1, 0.75)  # 超级加倍 加倍 阈值  (在地主是抢来的情况下)
        )
        self.FarmerJiabeiThreshold = (3, 1.5)
        self.FarmerJiabeiThresholdLow = (2, 1)
        self.MingpaiThreshold = 0.5
        self.stop_when_no_chaojia = True  # 是否在没有超级加倍的时候关闭自动模式
        self.use_manual_landlord_requirements = False  # 手动规则
        self.use_manual_mingpai_requirements = True  # Manual Mingpai
        # 坐标
        self.MyHandCardsPos = (180, 560, 1050, 90)  # 我的截图区域
        self.LPlayedCardsPos = (320, 280, 400, 120)  # 左边出牌截图区域
        self.RPlayedCardsPos = (720, 280, 400, 120)  # 右边出牌截图区域
        self.MPlayedCardsPos = (180, 420, 1050, 90)  # 我的出牌截图区域

        self.LandlordCardsPos = (600, 33, 220, 103)  # 地主底牌截图区域
        self.LPassPos = (360, 360, 120, 80)  # 左边不出截图区域
        self.RPassPos = (940, 360, 120, 80)  # 右边不出截图区域
        self.MPassPos = (636, 469, 152, 87)  # 我的不出截图区域

        self.PassBtnPos = (200, 450, 1000, 120)  # 要不起截图区域
        self.GeneralBtnPos = (200, 450, 1000, 120)  # 叫地主、抢地主、加倍按钮截图区域
        self.LandlordFlagPos = [(1247, 245, 48, 52), (12, 661, 51, 53), (123, 243, 52, 54)]  # 地主标志截图区域(右-我-左)
        self.blue_cards_num = [(273, 388, 33, 42), (1117, 387, 33, 44)]  # 加倍阶段上家和下家的牌数显示区域
        # Game Log Variables
        self.GameRecord = []
        self.game_type = ""
        self.initial_cards = ""
        self.initial_bid_rate = ""
        self.initial_model_rate = ""
        self.initial_mingpai = ""
        self.initial_multiply = ""
        # -------------------
        self.shouldExit = 0  # 通知上一轮记牌结束
        self.modeType = 1  # {1: resnet, 2: WP, 3: ADP}

        self.card_play_model_path_dict = {
            'landlord': "baselines/resnet/resnet_landlord.ckpt",
            'landlord_up': "baselines/resnet/resnet_landlord_up.ckpt",
            'landlord_down': "baselines/resnet/resnet_landlord_down.ckpt"
        }
        self.card_play_wp_model_path = {
            'landlord': "baselines/douzero_WP/landlord.ckpt",
            'landlord_up': "baselines/douzero_WP/landlord_up.ckpt",
            'landlord_down': "baselines/douzero_WP/landlord_down.ckpt"
        }
        self.card_play_adp_model_path = {
            'landlord': "baselines/douzero_ADP/landlord.ckpt",
            'landlord_up': "baselines/douzero_ADP/landlord_up.ckpt",
            'landlord_down': "baselines/douzero_ADP/landlord_down.ckpt"
        }

        if self.modeType == 1:
            LandlordModel.init_model("baselines/resnet/resnet_landlord.ckpt")
        elif self.modeType == 2:
            LandlordModel.init_model("baselines/douzero_WP/landlord.ckpt")
        elif self.modeType == 3:
            LandlordModel.init_model("baselines/douzero_ADP/landlord.ckpt")
        else:
            LandlordModel.init_model("baselines/resnet/resnet_landlord.ckpt")

    def hand_game(self):
        self.auto_sign = False
        self.AutoButton.setStyleSheet('background-color: rgba(255, 85, 255, 0);')
        self.HandButton.setStyleSheet('background-color: rgba(0, 0, 255, 0.5);')
        print("\n开启手动模式")
        if self.firt_time == 0:
            self.firt_time += 1
            self.loop_sign = 1
            self.stop_sign = 0
            while True:
                if self.stop_sign == 1:
                    break
                self.detect_start_btn()
                self.before_start()
                self.init_cards()
                self.sleep(5000)

    def auto_game(self):
        self.auto_sign = True
        self.AutoButton.setStyleSheet('background-color: rgba(255, 85, 255, 0.5);')
        self.HandButton.setStyleSheet('background-color: rgba(255, 85, 255, 0);')
        print("\n开启自动模式")
        if self.firt_time == 0:
            self.firt_time += 1
            self.loop_sign = 1
            self.stop_sign = 0
            while True:
                if self.stop_sign == 1:
                    break
                self.detect_start_btn()
                self.before_start()
                self.init_cards()
                self.sleep(4000)

    def game_loop(self):
        self.auto_sign = True
        self.loop_sign = 1
        self.stop_sign = 0
        while True:
            if self.stop_sign == 1:
                break
            self.detect_start_btn()
            self.before_start()
            self.init_cards()
            self.sleep(5000)

    def stop(self):
        if self.loop_sign == 1:
            pid = os.getpid()  # 获取当前进程的PID
            os.kill(pid, signal.SIGTERM)  # 主动结束指定ID的程序运行
        else:
            if self.in_game_flag:
                print("结束")
                try:
                    self.RunGame = False
                    self.loop_sign = 0
                    self.env.reset()
                    self.init_display()
                    self.env.game_over = True

                except AttributeError as e:
                    traceback.print_exc()

    def init_display(self):
        self.WinRate.setText("评分")
        self.WinRate.setStyleSheet('background-color: rgba(255, 85, 0, 0);')
        self.label.setText("游戏状态")
        self.BidWinrate.setText("叫牌得分")
        self.PreWinrate.setText("局前得分")
        self.label.setStyleSheet('background-color: rgba(255, 0, 0, 0);')
        self.UserHandCards.setText("手牌")
        self.textEdit.clear()
        self.LPlayedCard.setText("上家出牌区域")
        self.RPlayedCard.setText("下家出牌区域")
        self.PredictedCard.setText("AI出牌区域")
        self.ThreeLandlordCards.setText("底牌")
        self.recorder2zero()
        for player in self.Players:
            player.setStyleSheet('background-color: rgba(0, 255, 0, 0);')
        if self.firt_time == 0:
            self.AutoButton.setStyleSheet('background-color: rgba(255, 85, 255, 0);')
            self.HandButton.setStyleSheet('background-color: rgba(255, 85, 255, 0);')

    def init_cards(self):
        print("进入出牌前的阶段")
        self.RunGame = True
        GameHelper.Interrupt = False
        self.initial_model_rate = 0
        self.user_hand_cards_real = ""
        self.user_hand_cards_env = []
        # 其他玩家出牌
        self.my_played_cards_real = ""
        self.my_played_cards_env = []
        self.other_played_cards_real = ""
        self.other_played_cards_env = []
        # 其他玩家手牌（整副牌减去玩家手牌，后续再减掉历史出牌）
        self.other_hand_cards = []
        # 底牌
        self.three_landlord_cards_real = ""
        self.three_landlord_cards_env = []
        # 玩家角色代码：0-地主上家, 1-地主, 2-地主下家
        self.user_position_code = None
        self.user_position = ""
        # 开局时三个玩家的手牌
        self.card_play_data_list = {}

        # 识别三张底牌
        self.three_landlord_cards_real = self.find_landlord_cards()
        print("正在识别底牌", end="")
        while len(self.three_landlord_cards_real) != 3:
            print(".", end="")
            self.detect_start_btn()
            if not self.RunGame:
                break
            self.sleep(200)
            self.three_landlord_cards_real = self.find_landlord_cards()
        print("\n底牌： ", self.three_landlord_cards_real)
        self.ThreeLandlordCards.setText("底牌：" + self.three_landlord_cards_real)
        self.three_landlord_cards_env = [RealCard2EnvCard[c] for c in list(self.three_landlord_cards_real)]

        # 识别玩家的角色
        self.sleep(500)
        if self.user_position_code is None:
            self.user_position_code = self.find_landlord(self.LandlordFlagPos)
            while self.user_position_code is None:
                self.detect_start_btn()
                if not self.RunGame:
                    break
                print("正在识别玩家角色")
                self.sleep(200)
                self.user_position_code = self.find_landlord(self.LandlordFlagPos)

        # print("正在出牌人的代码： ", self.user_position_code)
        self.user_position = ['landlord_up', 'landlord', 'landlord_down'][self.user_position_code]
        print("\n我现在的角色是：", self.user_position)
        for player in self.Players:
            player.setStyleSheet('background-color: rgba(0, 255, 0, 0);')
        self.Players[self.user_position_code].setStyleSheet('background-color: rgba(0, 255, 0, 0.5);')

        # 识别玩家手牌
        self.user_hand_cards_real = self.find_my_cards()
        if self.user_position_code == 1:
            while len(self.user_hand_cards_real) != 20:
                self.detect_start_btn()
                if not self.RunGame:
                    break
                self.sleep(200)
                self.user_hand_cards_real = self.find_my_cards()
            self.user_hand_cards_env = [RealCard2EnvCard[c] for c in list(self.user_hand_cards_real)]
        else:
            while len(self.user_hand_cards_real) != 17:
                self.detect_start_btn()
                if not self.RunGame:
                    break
                self.sleep(200)
                self.user_hand_cards_real = self.find_my_cards()
            self.user_hand_cards_env = [RealCard2EnvCard[c] for c in list(self.user_hand_cards_real)]
        self.UserHandCards.setText(self.user_hand_cards_real)

        # 整副牌减去玩家手上的牌，就是其他人的手牌,再分配给另外两个角色（如何分配对AI判断没有影响）
        for i in set(AllEnvCard):
            self.other_hand_cards.extend([i] * (AllEnvCard.count(i) - self.user_hand_cards_env.count(i)))
        self.other_hands_cards_str = str(''.join([EnvCard2RealCard[c] for c in self.other_hand_cards]))[::-1]
        self.cards_recorder(self.other_hands_cards_str)
        self.card_play_data_list.update({
            'three_landlord_cards': self.three_landlord_cards_env,
            ['landlord_up', 'landlord', 'landlord_down'][(self.user_position_code + 0) % 3]:
                self.user_hand_cards_env,
            ['landlord_up', 'landlord', 'landlord_down'][(self.user_position_code + 1) % 3]:
                self.other_hand_cards[0:17] if (self.user_position_code + 1) % 3 != 1 else self.other_hand_cards[17:],
            ['landlord_up', 'landlord', 'landlord_down'][(self.user_position_code + 2) % 3]:
                self.other_hand_cards[0:17] if (self.user_position_code + 1) % 3 == 1 else self.other_hand_cards[17:]
        })

        print("开始对局")
        print("手牌:", self.user_hand_cards_real)
        print("底牌:", self.three_landlord_cards_real)

        # 出牌顺序：0-玩家出牌, 1-玩家下家出牌, 2-玩家上家出牌
        self.play_order = 0 if self.user_position == "landlord" else 1 if self.user_position == "landlord_up" else 2

        # 创建一个代表玩家的AI
        AI_Players = [0, 0]
        AI_Players[0] = self.user_position
        AI_Players[1] = DeepAgent(self.user_position, self.card_play_model_path_dict[self.user_position])

        '''ADP_Players = [0, 0]
        ADP_Players[0] = self.user_position
        ADP_Players[1] = DeepAgent(self.user_position, self.card_play_adp_model_path[self.user_position])'''

        self.env = GameEnv(AI_Players)

        try:
            self.start()
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            traceback.print_tb(exc_tb)
            print("游戏结束, 等待下一局")

    def sleep(self, ms):
        self.counter.restart()
        while self.counter.elapsed() < ms:
            QtWidgets.QApplication.processEvents(QEventLoop.AllEvents, 50)

    def start(self):
        self.my_pass_sign = False
        self.textEdit.clear()
        # print("现在的出牌顺序是谁：0是我；1是下家；2是上家：", self.play_order)
        self.env.card_play_init(self.card_play_data_list)
        print("开始对局")
        self.label.setText("游戏开始")
        self.label.setStyleSheet('background-color: rgba(255, 0, 0, 0.5);')
        first_run = True
        self.textEdit.append("底牌：" + self.three_landlord_cards_real)
        self.textEdit.append("手牌: " + self.user_hand_cards_real)
        self.textEdit.append("    ----- 开始对局 -----")
        self.textEdit.append("   上家       AI      下家")
        while not self.env.game_over:
            self.detect_start_btn()
            if not self.RunGame:
                break
            if self.play_order == 0:
                if self.auto_sign:
                    self.PredictedCard.setText("...")
                    action_message, action_list = self.env.step(self.user_position)
                    score = float(action_message['win_rate'])
                    if "resnet" in self.card_play_model_path_dict[self.user_position]:
                        score *= 8
                    self.UserHandCards.setText("手牌：" + str(''.join(
                        [EnvCard2RealCard[c] for c in self.env.info_sets[self.user_position].player_hand_cards]))[::-1])
                    action_list = action_list[:3]
                    self.winrate += float(action_list[0][1])
                    self.BidWinrate.setText("目前得分：" + str(round(self.winrate, 3)))
                    self.PredictedCard.setText(action_message["action"] if action_message["action"] else "不出")
                    self.PredictedCard.setStyleSheet('background-color: rgba(0, 255, 0, 0.5);')
                    action_list_str = " | ".join([ainfo[0] + " = " + ainfo[1] for ainfo in action_list])
                    self.WinRate.setText(action_list_str)
                    self.WinRate.setStyleSheet('background-color: rgba(255, 85, 0, 0.4);')
                    hand_cards_str = ''.join(
                        [EnvCard2RealCard[c] for c in self.env.info_sets[self.user_position].player_hand_cards])
                    if first_run:
                        self.initial_model_rate = round(float(action_message["win_rate"]), 3)  # win_rate at start
                        first_run = False
                    print("出牌:", action_message["action"] if action_message["action"] else "Pass", "| 得分:",
                          round(action_message["win_rate"], 4), "| 剩余手牌:", hand_cards_str)
                    print(action_list_str)
                    if action_message["action"] == "":
                        result = helper.LocateOnScreen("pass_btn", region=self.PassBtnPos, confidence=0.7)
                        passSign = helper.LocateOnScreen("yaobuqi", region=self.GeneralBtnPos, confidence=0.7)
                        buchu = helper.LocateOnScreen("buchu", region=self.MPassPos)
                        while result is None and passSign is None and buchu is None:
                            self.detect_start_btn()
                            if not self.RunGame or not self.auto_sign:
                                break
                            result = helper.LocateOnScreen("pass_btn", region=self.PassBtnPos, confidence=0.7)
                            passSign = helper.LocateOnScreen("yaobuqi", region=self.GeneralBtnPos, confidence=0.7)
                            buchu = helper.LocateOnScreen("buchu", region=self.MPassPos)
                        self.textEdit.append("                " + "不出")

                        if not self.my_pass_sign:
                            if result is not None:
                                helper.ClickOnImage("pass_btn", region=self.PassBtnPos, confidence=0.7)
                                self.sleep(100)
                            if passSign is not None:
                                self.sleep(100)
                                helper.ClickOnImage("yaobuqi", region=self.GeneralBtnPos, confidence=0.7)
                            self.sleep(200)
                            if buchu is not None:
                                print("王炸！ 自动不出")
                        else:
                            self.my_pass_sign = False
                    else:
                        hand_cards_str = ''.join(
                            [EnvCard2RealCard[c] for c in self.env.info_sets[self.user_position].player_hand_cards])

                        result = helper.LocateOnScreen("play_card", region=self.PassBtnPos, confidence=0.7)
                        while result is None:
                            self.detect_start_btn()
                            if not self.RunGame or not self.auto_sign:
                                break
                            print("等待出牌按钮")
                            self.sleep(200)
                            result = helper.LocateOnScreen("play_card", region=self.PassBtnPos, confidence=0.7)
                        self.click_cards(action_message["action"])
                        self.sleep(200)

                        helper.ClickOnImage("play_card", region=self.PassBtnPos, confidence=0.7)
                        self.sleep(200)
                        result = helper.LocateOnScreen("play_card", region=self.PassBtnPos, confidence=0.7)
                        if result is not None:
                            self.click_cards(action_message["action"])
                            self.sleep(500)
                            helper.ClickOnImage("play_card", region=self.PassBtnPos, confidence=0.7)

                        if action_message["action"] == "DX":
                            self.sleep(10)
                        ani = self.animation(action_message["action"])
                        if ani:
                            self.sleep(500)
                        if len(hand_cards_str) == 0:
                            self.RunGame = False
                            try:
                                if self.env is not None:
                                    self.env.game_over = True
                                    self.env.reset()
                                self.init_display()
                                print("程序走到这里")
                            except AttributeError as e:
                                traceback.print_exc()
                            self.sleep(1000)
                            break

                    self.PredictedCard.setStyleSheet('background-color: rgba(0, 255, 0, 0);')
                    self.textEdit.append("                  " + action_message["action"])
                    self.sleep(50)
                    self.play_order = 1
                else:
                    print("现在是手动模式，请手动出牌")
                    play_sound("music/1.wav")
                    action_message, action_list = self.env.step(self.user_position, update=False)
                    score = float(action_message['win_rate'])

                    if len(action_list) > 0:
                        action_list = action_list[:3]
                        action_list_str = " | ".join([ainfo[0] + " = " + ainfo[1] for ainfo in action_list])
                        self.WinRate.setText(action_list_str)
                        self.WinRate.setStyleSheet('background-color: rgba(255, 85, 0, 0.4);')
                        self.winrate += float(action_list[0][1])
                        self.BidWinrate.setText("目前得分：" + str(round(score, 3)))
                    else:
                        self.WinRate.setText("自己看着出")

                    if first_run:
                        self.initial_model_rate = round(float(action_message["win_rate"]), 3)  # win_rate at start
                        first_run = False

                    self.PredictedCard.setText("等待自己出牌")
                    self.PredictedCard.setStyleSheet('background-color: rgba(0, 255, 0, 0.5);')
                    pass_flag = helper.LocateOnScreen('buchu', region=self.MPassPos)
                    centralCards = self.find_other_cards(self.MPlayedCardsPos)
                    print("等待自己出牌", end="")

                    have_ani = self.waitUntilNoAnimation()
                    if have_ani:
                        self.PredictedCard.setText("等待动画")
                        self.sleep(1000)

                    while len(centralCards) == 0 and pass_flag is None:
                        if not self.RunGame or self.auto_sign:
                            break
                        self.detect_start_btn()
                        print(".", end="")
                        self.sleep(100)
                        pass_flag = helper.LocateOnScreen('buchu', region=self.MPassPos)
                        centralCards = self.find_other_cards(self.MPlayedCardsPos)

                    pass_flag = helper.LocateOnScreen('buchu', region=self.MPassPos)
                    if pass_flag is None:
                        # 识别下家出牌
                        while True:
                            self.detect_start_btn()
                            if not self.RunGame or self.auto_sign:
                                break

                            centralOne = self.find_other_cards(self.MPlayedCardsPos)
                            self.sleep(100)
                            centralTwo = self.find_other_cards(self.MPlayedCardsPos)
                            if centralOne == centralTwo:
                                self.my_played_cards_real = centralOne
                                if ("X" in centralOne or "D" in centralOne) and not ("DX" in centralOne):
                                    self.sleep(500)
                                    self.my_played_cards_real = self.find_other_cards(self.MPlayedCardsPos)
                                # ani = self.animation(self.other_played_cards_real)
                                # if ani:
                                # self.RPlayedCard.setText("等待动画")
                                # self.sleep(500)
                                break
                        self.textEdit.append("                  " + self.my_played_cards_real)

                    else:
                        self.my_played_cards_real = ""
                        self.textEdit.append("                " + "不出")
                    print("\n自己出牌：", self.my_played_cards_real if self.my_played_cards_real else "pass")
                    self.my_played_cards_env = [RealCard2EnvCard[c] for c in list(self.my_played_cards_real)]
                    self.my_played_cards_env.sort()
                    self.env.step(self.user_position, self.my_played_cards_env)

                    self.UserHandCards.setText("手牌：" + str(''.join(
                        [EnvCard2RealCard[c] for c in self.env.info_sets[self.user_position].player_hand_cards]))[::-1])

                    self.PredictedCard.setText(self.my_played_cards_real if self.my_played_cards_real else "不出")
                    self.PredictedCard.setStyleSheet('background-color: rgba(0, 255, 0, 0.5);')

                    # 更新界面
                    self.PredictedCard.setText(self.my_played_cards_real if self.my_played_cards_real else "不出")
                    self.PredictedCard.setStyleSheet('background-color: rgba(0, 255, 0, 0);')
                    self.sleep(50)
                    self.play_order = 1

            elif self.play_order == 1:
                self.RPlayedCard.setText("等待下家出牌")
                self.RPlayedCard.setStyleSheet('background-color: rgba(0, 255, 0, 0.5);')
                pass_flag = helper.LocateOnScreen('buchu', region=self.RPassPos)
                rightCards = self.find_other_cards(self.RPlayedCardsPos)
                print("等待下家出牌", end="")

                have_ani = self.waitUntilNoAnimation()
                if have_ani:
                    self.RPlayedCard.setText("等待动画")
                    self.sleep(1000)

                while len(rightCards) == 0 and pass_flag is None:
                    if not self.RunGame:
                        break
                    self.detect_start_btn()
                    print(".", end="")
                    self.sleep(100)
                    pass_flag = helper.LocateOnScreen('buchu', region=self.RPassPos)
                    rightCards = self.find_other_cards(self.RPlayedCardsPos)

                pass_flag = helper.LocateOnScreen('buchu', region=self.RPassPos)
                if pass_flag is None:
                    # 识别下家出牌
                    while True:
                        self.detect_start_btn()
                        if not self.RunGame:
                            break

                        rightOne = self.find_other_cards(self.RPlayedCardsPos)
                        self.sleep(100)
                        rightTwo = self.find_other_cards(self.RPlayedCardsPos)
                        if rightOne == rightTwo:
                            if len(rightOne) > 0:
                                self.other_played_cards_real = rightOne

                                if "X" in rightOne or "D" in rightOne and not ("DX" in rightOne):
                                    self.sleep(500)
                                    self.other_played_cards_real = self.find_other_cards(self.RPlayedCardsPos)
                                    if self.other_played_cards_real == "DX":
                                        print("检测到王炸坏，延时0.5秒")
                                        self.sleep(500)
                                # ani = self.animation(self.other_played_cards_real)
                                # if ani:
                                # self.RPlayedCard.setText("等待动画")
                                # self.sleep(500)
                                break
                    self.textEdit.append("                            " + self.other_played_cards_real)

                else:
                    self.other_played_cards_real = ""
                    self.textEdit.append("                           " + "不出")
                print("\n下家出牌：", self.other_played_cards_real if self.other_played_cards_real else "pass")
                self.other_played_cards_env = [RealCard2EnvCard[c] for c in list(self.other_played_cards_real)]
                self.other_played_cards_env.sort()
                self.env.step(self.user_position, self.other_played_cards_env)
                # 更新界面
                self.RPlayedCard.setText(self.other_played_cards_real if self.other_played_cards_real else "不出")
                self.RPlayedCard.setStyleSheet('background-color: rgba(0, 255, 0, 0);')
                # self.other_hands_cards_str = self.other_hands_cards_str.replace(self.other_played_cards_real, "", 1)
                self.other_hands_cards_str = self.subtract_strings(self.other_hands_cards_str,
                                                                   self.other_played_cards_real)
                # print("记牌器：", self.other_hands_cards_str)
                self.cards_recorder(self.other_hands_cards_str)
                self.sleep(50)
                self.play_order = 2

            elif self.play_order == 2:
                self.LPlayedCard.setText("等待上家出牌")
                self.LPlayedCard.setStyleSheet('background-color: rgba(0, 255, 0, 0.5);')
                pass_flag = helper.LocateOnScreen('buchu', region=self.LPassPos)
                leftCards = self.find_other_cards(self.LPlayedCardsPos)
                print("等待上家出牌", end="")

                have_ani = self.waitUntilNoAnimation()
                if have_ani:
                    self.LPlayedCard.setText("等待动画")
                    self.sleep(1000)

                while len(leftCards) == 0 and pass_flag is None:
                    self.detect_start_btn()
                    if not self.RunGame:
                        break
                    print(".", end="")
                    self.sleep(100)
                    pass_flag = helper.LocateOnScreen('buchu', region=self.LPassPos)
                    leftCards = self.find_other_cards(self.LPlayedCardsPos)

                pass_flag = helper.LocateOnScreen('buchu', region=self.LPassPos)
                if pass_flag is None:
                    # 识别上家出牌
                    while True:
                        self.detect_start_btn()
                        if not self.RunGame:
                            break

                        '''result = helper.LocateOnScreen('buchu', region=self.MPassPos)
                        if result is not None:
                            self.my_pass_sign = True
                            print("\n**************  解决能走不走的BUG  **************")'''

                        leftOne = self.find_other_cards(self.LPlayedCardsPos)
                        self.sleep(100)
                        leftTwo = self.find_other_cards(self.LPlayedCardsPos)
                        if leftOne == leftTwo:
                            if len(leftOne) > 0:
                                self.other_played_cards_real = leftOne

                                if ("X" in leftOne or "D" in leftOne) and not ("DX" in leftOne):
                                    self.sleep(500)
                                    self.other_played_cards_real = self.find_other_cards(self.LPlayedCardsPos)
                                    if self.other_played_cards_real == "DX":
                                        print("检测到王炸，延时0.5秒")
                                        self.sleep(500)

                                # ani = self.animation(self.other_played_cards_real)
                                # if ani:
                                # self.LPlayedCard.setText("等待动画")
                                # self.sleep(500)
                                break
                    self.textEdit.append("    " + self.other_played_cards_real)

                else:
                    self.other_played_cards_real = ""
                    self.textEdit.append("   " + "不出")
                print("\n上家出牌：", self.other_played_cards_real if self.other_played_cards_real else "pass")
                self.other_played_cards_env = [RealCard2EnvCard[c] for c in list(self.other_played_cards_real)]
                self.other_played_cards_env.sort()
                self.env.step(self.user_position, self.other_played_cards_env)

                # 更新界面
                self.LPlayedCard.setText(self.other_played_cards_real if self.other_played_cards_real else "不出")
                self.LPlayedCard.setStyleSheet('background-color: rgba(0, 255, 0, 0);')
                self.other_hands_cards_str = self.subtract_strings(self.other_hands_cards_str,
                                                                   self.other_played_cards_real)
                # print("记牌器：", self.other_hands_cards_str)
                self.cards_recorder(self.other_hands_cards_str)
                self.sleep(50)
                self.play_order = 0

        if self.loop_sign == 0:
            self.stop()
            print("这里有问题")
        self.label.setText("游戏结束")
        self.label.setStyleSheet('background-color: rgba(255, 0, 0, 0);')
        self.init_display()
        print("本局已结束\n")
        self.sleep(5000)

    def detect_start_btn(self):
        beans = [(308, 204, 254, 60), (295, 474, 264, 60), (882, 203, 230, 60)]
        for i in beans:
            result = helper.LocateOnScreen("over", region=i, confidence=0.9)
            if result is not None:
                print("豆子出现，对局结束")
                self.RunGame = False
                self.init_display()
                try:
                    if self.env is not None:
                        self.env.game_over = True
                        self.env.reset()
                    self.init_display()
                    print("程序走到这里")
                except AttributeError as e:
                    traceback.print_exc()
                in_game = helper.LocateOnScreen("chat", region=(1302, 744, 117, 56))
                print("还未重新开局", end="")
                while in_game is not None:
                    self.sleep(500)
                    print(".", end="")
                    in_game = helper.LocateOnScreen("chat", region=(1302, 744, 117, 56))
                print("\n等待开始下一局")
                break

        if self.auto_sign:
            result = helper.LocateOnScreen("continue", region=(1100, 617, 200, 74))
            if result is not None:
                if self.loop_sign == 0:
                    print("本局游戏已结束")
                    self.label.setText("游戏结束")
                    self.label.setStyleSheet('background-color: rgba(255, 0, 0, 0.5);')
                    self.stop()
                else:
                    self.RunGame = True
                    helper.ClickOnImage("continue", region=(1100, 617, 200, 74))
                    self.sleep(100)
                    try:
                        if self.env is not None:
                            self.env.game_over = True
                            self.env.reset()
                        self.init_display()
                    except AttributeError as e:
                        traceback.print_exc()

            result = helper.LocateOnScreen("start_game", region=(720, 466, 261, 117))
            if result is not None:
                helper.ClickOnImage("start_game", region=(720, 466, 261, 117))
                self.sleep(1000)

            result = helper.LocateOnScreen("tuoguan", region=(577, 613, 271, 128))
            if result is not None:
                helper.ClickOnImage("tuoguan", region=(577, 613, 271, 128))
                self.sleep(1000)

            result = helper.LocateOnScreen("sure", region=(657, 500, 216, 72))
            if result is not None:
                helper.ClickOnImage("sure", region=(657, 500, 216, 72))
                self.sleep(1000)

            result = helper.LocateOnScreen("good", region=(434, 599, 219, 88))
            if result is not None:
                helper.ClickOnImage("good", region=(434, 599, 219, 88))
                self.sleep(1000)

            result = helper.LocateOnScreen("zhidao", region=(593, 543, 224, 94))
            if result is not None:
                helper.ClickOnImage("zhidao", region=(593, 543, 224, 94))
                self.sleep(1000)

            result = helper.LocateOnScreen("chacha", region=(1036, 65, 300, 230))
            if result is not None:
                helper.ClickOnImage("chacha", region=(1036, 65, 300, 230))
                self.sleep(1000)
        else:
            pass

    def cards_filter(self, location, distance):  # 牌检测结果滤波
        if len(location) == 0:
            return 0
        locList = [location[0][0]]
        poslist = [location[0]]
        count = 1
        for e in location:
            flag = 1  # “是新的”标志
            for have in locList:
                # print(abs(e[0] - have))
                if abs(e[0] - have) <= distance:
                    flag = 0
                    break
            if flag:
                count += 1
                locList.append(e[0])
                poslist.append(e)
        # print(poslist)
        return count, poslist

    def find_cards(self, img, pos, mark="", confidence=0.8):
        cards_real = ""
        D_king = 0
        X_king = 0
        for card in AllCards:
            result = gh.LocateAllOnImage(img, helper.PicsCV[mark + card], region=pos, confidence=confidence)

            if len(result) > 0:
                count, s = self.cards_filter(list(result), 30)
                if card == "X" or card == "D":
                    for a in s:
                        classifier = DC.ColorClassify(debug=True)
                        img1 = img[pos[1]:pos[1] + pos[3], pos[0]:pos[0] + pos[2]]
                        img2 = img1[a[1]:a[1] + a[3] - 50, a[0]:a[0] + 20]  # 注意连着裁切时img不能重名
                        # gh.ShowImg(img2)
                        result = classifier.classify(img2)
                        # print(result)
                        for b in result:
                            if b[0] == "Red":
                                if b[1] > 0.54:
                                    D_king = 1
                                else:
                                    X_king = 1
                else:
                    cards_real += card[0] * count

        if X_king:
            cards_real += "X"
            cards_real = cards_real[-1] + cards_real[:-1]

        if D_king:
            cards_real += "D"
            cards_real = cards_real[-1] + cards_real[:-1]
        return cards_real

    def find_my_cards(self):
        img, _ = helper.Screenshot()
        img = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
        my_cards_real = self.find_cards(img, self.MyHandCardsPos, mark="m")
        return my_cards_real

    def find_other_cards(self, pos):
        img, _ = helper.Screenshot()
        img = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
        other_cards_real = self.find_cards(img, pos, mark="o")
        return other_cards_real

    def find_landlord_cards(self):
        img, _ = helper.Screenshot()
        img = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
        landlord__cards_real = self.find_cards(img, self.LandlordCardsPos, mark="z",
                                               confidence=self.ThreeLandlordCardsConfidence)
        return landlord__cards_real

    def click_cards(self, out_cards):
        cards = self.find_my_cards()
        num = len(cards)
        space = 45.6
        res1 = helper.LocateOnScreen("up_left", region=self.MyHandCardsPos, confidence=0.65)
        while res1 is None:
            self.detect_start_btn()
            if not self.RunGame:
                break
            print("未找到手牌区域")
            self.sleep(500)
            res1 = helper.LocateOnScreen("up_left", region=self.MyHandCardsPos, confidence=0.65)
        pos = res1[0] + 6, res1[1] + 7

        res2 = helper.LocateOnScreen("up_left", region=(180, 580, 1050, 90), confidence=0.65)
        if res2 is not None:
            pos = res1[0] + 6, res1[1] + 7

        pos_list = [(int(pos[0] + i * space), pos[1]) for i in range(num)]

        # 将两个列表合并转为字典
        cards_dict = defaultdict(list)
        for key, value in zip(cards, pos_list):
            cards_dict[key].append(value)
        # 转换为普通的字典
        cards_dict = dict(cards_dict)
        remove_dict = {key: [] for key in cards_dict.keys()}
        # print(cards_dict)
        if out_cards == "DX":
            helper.LeftClick2((cards_dict["X"][0][0] + 20, 650))
            self.sleep(500)

        else:
            for i in out_cards:
                cars_pos = cards_dict[i][-1][0:2]

                # print("准备点击的牌：", cards_dict[i])
                point = cars_pos[0] + 20, cars_pos[1] + 100
                img, _ = helper.Screenshot()
                img = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
                check_one = self.find_cards(img=img, pos=(cars_pos[0] - 2, 565, 60, 60), mark="m", confidence=0.8)
                # print("系统帮你点的牌：", check_one, "你要出的牌：", i)

                if check_one == i and check_one != "D" and check_one != "X":
                    print("腾讯自动帮你选牌：", check_one)

                else:
                    helper.LeftClick2(point)
                    # print(point)
                    self.sleep(100)
                remove_dict[i].append(cards_dict[i][-1])
                cards_dict[i].remove(cards_dict[i][-1])
                # print("remove_dict", remove_dict)
            img, _ = helper.Screenshot()
            img = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
            check_cards = self.find_cards(img, (180, 590, 1050, 90), mark="m")
            for i in out_cards:
                cards = cards.replace(i, "", 1)
            # print("检查剩的牌： ", check_cards, "应该剩的牌： ", cards)
            if len(check_cards) < len(cards):
                for m in check_cards:
                    cards = cards.replace(m, "", 1)
                # print("系统多点的牌： ", cards)
                for n in cards:
                    # print("字典里还剩的牌： ", cards_dict)
                    cars_pos2 = cards_dict[n][-1][0:2]
                    # print("准备点回来的牌：", cars_pos2)
                    point2 = cars_pos2[0] + 20, cars_pos2[1] + 100
                    helper.LeftClick2(point2)
                    self.sleep(100)
                    remove_dict[n].append(cards_dict[n][-1])
                    cards_dict[n].remove(cards_dict[n][-1])
            elif len(check_cards) > len(cards):
                for m in cards:
                    check_cards = check_cards.replace(m, "", 1)
                # print("系统少点的牌： ", check_cards)
                for n in check_cards:
                    # print("删除的字典： ", remove_dict)
                    cars_pos3 = remove_dict[n][0][0:2]
                    # print("准备再点出去的牌：", cars_pos3)
                    point3 = cars_pos3[0] + 20, cars_pos3[1] + 100
                    helper.LeftClick2(point3)
                    self.sleep(300)
                    remove_dict[n].remove(remove_dict[n][0])
                    # print(remove_dict)
            self.sleep(200)

    def landlord_code(self):
        user_position_code = None
        for i in range(5):
            num_left = get_ocr_cards(self.blue_cards_num[0])
            num_right = get_ocr_cards(self.blue_cards_num[1])
            if (num_left == 17 or num_left == 20) and (num_right == 17 or num_right == 20):
                if num_left == 20:
                    user_position_code = 2
                elif num_right == 20:
                    user_position_code = 0
                elif num_left == 17 and num_right == 17:
                    user_position_code = 1
                print("加倍时第 {} 次找地主的位置".format(i + 1))
                break
            self.sleep(200)
        return user_position_code

    def find_landlord(self, landlord_flag_pos):
        print("第一种方法找地主位置")
        code = self.landlord_code()
        if code in [0, 1, 2]:
            print("地主的位置代码是： ", code)
            return code
        else:
            print("第二种方法找地主位置")
            img, _ = helper.Screenshot()
            img = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2HSV)
            for pos in landlord_flag_pos:
                classifier = DC.ColorClassify(debug=True)
                imgCut = img[pos[1]:pos[1] + pos[3], pos[0]:pos[0] + pos[2]]
                result = classifier.classify(imgCut)
                for b in result:
                    if b[0] == "Orange":
                        if b[1] > 0.75:
                            return landlord_flag_pos.index(pos)
                self.sleep(100)

    def before_start(self):
        global win_rate, initialBeishu, cards_str
        self.RunGame = True
        GameHelper.Interrupt = True
        have_bid = False
        is_stolen = 0
        self.in_game_flag = False
        self.initial_multiply = 0
        self.initial_mingpai = 0
        self.initial_bid_rate = 0
        self.buy_chaojijiabei_flag = False
        self.label.setText("叫地主阶段")
        self.label.setStyleSheet('background-color: rgba(255, 0, 0, 0.5);')

        print("还没进入到游戏中", end='')
        in_game = helper.LocateOnScreen("chat", region=(1302, 744, 117, 56))
        while in_game is None:
            self.detect_start_btn()
            if not self.RunGame:
                break
            self.sleep(1000)
            print(".", end="")
            self.label.setText("未进入游戏")
            self.label.setStyleSheet('background-color: rgba(255, 0, 0, 0.5);')
            in_game = helper.LocateOnScreen("chat", region=(1302, 744, 117, 56))
        self.in_game_flag = True
        self.sleep(300)
        if self.in_game_flag:
            print("\n进入到游戏场内")
            print("游戏未开始", end="")
            laotou = helper.LocateOnScreen("laotou", region=self.LandlordCardsPos)
            while laotou is None:
                self.detect_start_btn()
                if not self.RunGame:
                    break
                self.sleep(500)
                print(".", end="")
                self.label.setText("游戏未开始")
                self.label.setStyleSheet('background-color: rgba(255, 0, 0, 0.5);')
                laotou = helper.LocateOnScreen("laotou", region=self.LandlordCardsPos)

            print("\n游戏开始")
            self.label.setText("游戏未开始")
            self.label.setStyleSheet('background-color: rgba(255, 0, 0, 0.5);')

        if self.auto_sign:
            while self.RunGame and self.auto_sign:
                outterBreak = False
                jiaodizhu_btn = helper.LocateOnScreen("jiaodizhu_btn", region=self.GeneralBtnPos)
                qiangdizhu_btn = helper.LocateOnScreen("qiangdizhu_btn", region=self.GeneralBtnPos)
                jiabei_btn = helper.LocateOnScreen("jiabei_btn", region=self.GeneralBtnPos)
                self.detect_start_btn()
                print("等待加倍或叫地主", end="")
                while jiaodizhu_btn is None and qiangdizhu_btn is None and jiabei_btn is None:
                    self.detect_start_btn()
                    if not self.RunGame or not self.auto_sign:
                        break
                    print(".", end="")
                    self.sleep(100)
                    jiaodizhu_btn = helper.LocateOnScreen("jiaodizhu_btn", region=self.GeneralBtnPos)
                    qiangdizhu_btn = helper.LocateOnScreen("qiangdizhu_btn", region=self.GeneralBtnPos)
                    jiabei_btn = helper.LocateOnScreen("jiabei_btn", region=self.GeneralBtnPos)
                if jiabei_btn is None:
                    cards = self.find_my_cards()
                    while len(cards) != 17 and len(cards) != 20:
                        self.detect_start_btn()
                        if not self.RunGame or not self.auto_sign:
                            break
                        self.sleep(200)
                        cards = self.find_my_cards()
                    cards_str = "".join([card[0] for card in cards])
                    self.UserHandCards.setText(cards_str)
                    win_rate = BidModel.predict_score(cards_str)
                    farmer_score = FarmerModel.predict(cards_str, "farmer")

                    self.BidWinrate.setText("叫牌得分: " + str(round(win_rate, 3)))
                    self.PreWinrate.setText("不叫得分: " + str(round(farmer_score, 3)))
                    self.sleep(10)
                    self.initial_bid_rate = round(win_rate, 3)
                    is_stolen = 0
                    compare_winrate = win_rate
                    if compare_winrate > 0:
                        compare_winrate *= 2.5
                    landlord_requirement = True

                    if jiaodizhu_btn is not None:
                        print("\n***** 叫地主阶段 *****")
                        have_bid = True
                        if win_rate > self.BidThresholds[0] and landlord_requirement and not (
                                win_rate < 0 and farmer_score > 0.75):
                            helper.ClickOnImage("jiaodizhu_btn", region=self.GeneralBtnPos)
                            print("叫地主")

                        else:
                            helper.ClickOnImage("bujiao_btn", region=self.GeneralBtnPos)
                            print("不叫地主")
                    elif qiangdizhu_btn is not None:
                        print("\n***** 抢地主阶段 *****")
                        is_stolen = 1
                        if have_bid:
                            threshold_index = 1
                        else:
                            threshold_index = 2
                        if win_rate > self.BidThresholds[threshold_index] and landlord_requirement and not (
                                win_rate < 0 and farmer_score > 0.75):
                            helper.ClickOnImage("qiangdizhu_btn", region=self.GeneralBtnPos)
                            print("抢地主")
                        else:
                            helper.ClickOnImage("buqiang_btn", region=self.GeneralBtnPos)
                            print("不抢地主")
                        have_bid = True
                    else:
                        pass
                else:
                    print("\n***** 加倍阶段 *****")
                    self.label.setText("加倍阶段")
                    self.label.setStyleSheet('background-color: rgba(255, 0, 0, 0.5);')
                    print("加倍阶段")
                    st = time.time()
                    # 识别加倍数
                    initialBeishu = get_ocr_fast()
                    end = time.time()
                    print("InitialBeishu:", initialBeishu)
                    print("OCR Used Time:", end - st)
                    st30 = time.time()
                    llcards = self.find_landlord_cards()
                    print("底牌未识别", end="")
                    while len(llcards) != 3:
                        self.detect_start_btn()
                        if not self.RunGame or not self.auto_sign:
                            break
                        print(".", end="")
                        if len(llcards) > 3:
                            if self.ThreeLandlordCardsConfidence < 0.8:
                                self.ThreeLandlordCardsConfidence += 0.05
                                time.sleep(200)
                        elif len(llcards) < 3:
                            if self.ThreeLandlordCardsConfidence > 0.6:
                                self.ThreeLandlordCardsConfidence -= 0.05
                                time.sleep(200)
                        print(".", end="")
                        llcards = self.find_landlord_cards()
                    print("\n底牌:", llcards)
                    cards = self.find_my_cards()
                    while len(cards) != 17 and len(cards) != 20:
                        self.detect_start_btn()
                        if not self.RunGame or not self.auto_sign:
                            break
                        self.sleep(200)
                        cards = self.find_my_cards()
                    cards_str = "".join([card[0] for card in cards])
                    self.UserHandCards.setText(cards_str)
                    print("识别自己的牌用时:", time.time() - st30)

                    self.initial_cards = cards_str
                    if len(cards_str) == 20:
                        # win_rate = LandlordModel.predict(cards_str)
                        # model_path = self.card_play_model_path_dict["landlord"]
                        # wp_model_path = self.card_play_wp_model_path["landlord"]
                        # if not self.have_bomb(cards_env):
                        #     print("地主无炸")
                        #     LandlordModel.init_model2(model_path, wp_model_path)
                        # else:
                        #     LandlordModel.init_model(model_path)
                        #     print("地主有炸")
                        # LandlordModel.init_model(model_path) # not considering wp when no bomb
                        print("cards_str, llcards", cards_str, llcards)
                        win_rate = LandlordModel.predict_by_model(cards_str, llcards)
                        self.PreWinrate.setText("局前得分: " + str(round(win_rate, 3)))
                        print("预估地主得分:", round(win_rate, 3))
                    else:
                        st20 = time.time()
                        user_position_code = self.find_landlord(self.LandlordFlagPos)
                        while user_position_code is None:
                            self.detect_start_btn()
                            if not self.RunGame:
                                break
                            self.sleep(200)
                            user_position_code = self.find_landlord(self.LandlordFlagPos)
                        self.user_position_code = user_position_code
                        print("识别地主位置用时", time.time() - st20)

                        st40 = time.time()
                        user_position = ['up', 'landlord', 'down'][user_position_code]
                        win_rate = FarmerModel.predict(cards_str, user_position)
                        print("预估农民得分:", round(win_rate, 3))
                        self.PreWinrate.setText("局前得分: " + str(round(win_rate, 3)))
                        print("预测出牌用时:", time.time() - st40)
                    if len(cards_str) == 20:
                        JiabeiThreshold = self.JiabeiThreshold[is_stolen]
                    else:
                        JiabeiThreshold = self.FarmerJiabeiThreshold
                    print("休息前共用时:", time.time() - st)

                    if len(cards_str) == 17:
                        self.sleep(500)
                        print("Farmer休息 0.5 秒, 观察他人加倍")
                    else:
                        self.sleep(1000)
                        print("Landlord休息 1 秒, 观察他人加倍")
                    #  识别加倍数
                    currentBeishu = get_ocr_fast()
                    print("CurrentBeishu:", currentBeishu, "倍")
                    try:
                        if float(currentBeishu) >= 2.5 * float(initialBeishu) and win_rate < 0.7:
                            print("倍数高于2.5且我方胜率小于1，放弃加倍")
                            outterBreak = True
                            break
                        elif float(currentBeishu) >= 1.5 * float(initialBeishu) and win_rate < 0:
                            print("对方加倍，我方牌力小于0，放弃加倍")
                            outterBreak = True
                            break
                    except Exception as e:
                        print("检测加倍出现错误，继续运行")
                        traceback.print_exc()

                    if (float(currentBeishu) == float(initialBeishu)) and len(cards_str) == 17:  # 如果对方虚了没有加倍，那么我方准备加倍
                        JiabeiThreshold = self.FarmerJiabeiThresholdLow

                    chaojijiabei_btn = helper.LocateOnScreen("chaojijiabei_btn", region=self.GeneralBtnPos)
                    if chaojijiabei_btn is None:
                        self.buy_chaojijiabei_flag = True

                    # if chaojijiabei_btn is None and self.stop_when_no_chaojia:
                    #     self.AutoPlay = False
                    #     self.SwitchMode.setText("自动" if self.AutoPlay else "单局")
                    #     self.sleep(10)
                    #     print("检测到没有超级加倍卡，已停止自动模式")
                    if win_rate > JiabeiThreshold[0]:
                        chaojijiabei_btn = helper.LocateOnScreen("chaojijiabei_btn", region=self.GeneralBtnPos)
                        if chaojijiabei_btn is not None and (
                                len(cards_str) != 17 or (
                                'DX' in cards_str or 'D22' in cards_str) or currentBeishu <= 15):
                            helper.ClickOnImage("chaojijiabei_btn", region=self.GeneralBtnPos)
                            print("click超级加倍")
                            self.initial_multiply = 4
                        else:
                            helper.ClickOnImage("jiabei_btn", region=self.GeneralBtnPos)
                            print("加倍")
                            self.initial_multiply = 2
                    elif win_rate > JiabeiThreshold[1]:
                        print("加倍")
                        helper.ClickOnImage("jiabei_btn", region=self.GeneralBtnPos)
                        self.initial_multiply = 2
                    else:
                        print("不加倍")
                        helper.ClickOnImage("bujiabei_btn", region=self.GeneralBtnPos)
                        helper.LeftClick((840, 510))
                        self.initial_multiply = 0
                    outterBreak = True
                    break
                if outterBreak:
                    break

                # llcards = self.find_three_landlord_cards(self.ThreeLandlordCardsPos)
                # while len(llcards) != 3 and self.RunGame:
                #     print("等待底牌", llcards)
                #     if np.random.rand() > 0.9:
                #         self.detect_start_btn()
                #     else:
                #         self.sleep(50)
                #     llcards = self.find_three_landlord_cards(self.ThreeLandlordCardsPos)
                self.sleep(1000)
            if win_rate > self.MingpaiThreshold and len(cards_str) == 20 and self.initial_multiply == 4:
                # 识别加倍数
                currentBeishu = get_ocr_fast()
                print("CurrentBeishu:", currentBeishu, "倍")
                try:
                    print("InitialBeishu before Mingpai:", float(initialBeishu))
                    print("CurrentBeishu before Mingpai:", float(currentBeishu))
                    if float(currentBeishu) > float(initialBeishu) * 4 * 2:  # if someone chaojijiabei, don't mingpai
                        print("Someone Chaojiajiabei, Too risky to Mingpai")
                    else:
                        print("Going to Mingpai, Good Luck!")
                        helper.ClickOnImage("mingpai_btn", region=self.GeneralBtnPos)
                        self.initial_mingpai = 1
                except:
                    print("There are some problems with Mingpai, Please check")
                    pass
            self.winrate = win_rate
            print("自动叫地主结束")
            self.label.setText("加倍结束")
            self.label.setStyleSheet('background-color: rgba(255, 0, 0, 0.5);')
        else:
            print("现在是手动模式，请手动 | 叫地主| 抢地主 | 加倍 |")
            self.label.setStyleSheet('background-color: rgba(255, 0, 0, 0.5);')
            self.WinRate.setText("自己手动 |叫地主  抢地主  加倍|")
            self.WinRate.setStyleSheet('background-color: rgba(255, 85, 0, 0.4);')
            self.winrate = 0
            cards = self.find_my_cards()
            print("正在识别手牌", end="")
            while len(cards) != 17 and len(cards) != 20:
                print(".", end="")
                self.detect_start_btn()
                if not self.RunGame:
                    break
                self.sleep(200)
                cards = self.find_my_cards()
            cards_str = "".join([card[0] for card in cards])
            print("\n手牌： ", cards_str)
            self.UserHandCards.setText(cards_str)
            win_rate = BidModel.predict_score(cards_str)
            farmer_score = FarmerModel.predict(cards_str, "farmer")

            self.BidWinrate.setText("叫牌得分: " + str(round(win_rate, 3)))
            self.PreWinrate.setText("局前得分: " + str(round(farmer_score, 3)))
            self.label.setText("游戏开始")
            self.label.setStyleSheet('background-color: rgba(255, 0, 0, 0.5);')

            st30 = time.time()
            llcards = self.find_landlord_cards()
            print("底牌未识别", end="")
            while len(llcards) != 3:
                self.detect_start_btn()
                if not self.RunGame:
                    break
                print(".", end="")
                self.sleep(200)
                llcards = self.find_landlord_cards()
            print("\n底牌:", llcards)
            print("识别底牌用时:", time.time() - st30)

            st40 = time.time()
            cards = self.find_my_cards()
            while len(cards) != 17 and len(cards) != 20:
                self.detect_start_btn()
                if not self.RunGame or not self.auto_sign:
                    break
                self.sleep(200)
                cards = self.find_my_cards()
            cards_str = "".join([card[0] for card in cards])
            self.UserHandCards.setText(cards_str)
            print("识别自己的牌用时:", time.time() - st40)

            self.initial_cards = cards_str
            if len(cards_str) == 20:
                print("cards_str, llcards", cards_str, llcards)
                win_rate = LandlordModel.predict_by_model(cards_str, llcards)
                self.PreWinrate.setText("局前得分: " + str(round(win_rate, 3)))
                print("预估地主得分:", round(win_rate, 3))
            self.winrate = win_rate
            print("手动动叫地主结束")
            self.label.setText("加倍结束")

    def give_coffee(self, kind):
        helper.LeftClick((1000, 550))
        if kind == "right":
            print("Giving coffee to right")
            helper.MoveTo((1167, 293))
            self.sleep(1000)
            helper.LeftClick((920, 237))
            self.sleep(50)
        elif kind == "left":
            print("Giving coeffe to left")
            helper.MoveTo((260, 300))
            self.sleep(1000)
            helper.LeftClick((660, 237))
            self.sleep(50)
        elif kind == "both":
            self.give_coffee("left")
            self.sleep(500)
            self.give_coffee("right")
            self.sleep(100)

    def animation(self, cards):
        move_type = get_move_type(self.real_to_env(cards))
        animation_types = {4, 5, 13, 14, 8, 9, 10, 11, 12}
        if move_type["type"] in animation_types or len(cards) >= 6:
            return True

    def waitUntilNoAnimation(self, ms=100):
        ani = self.haveAnimation(ms)
        first_run = 0
        if ani:
            print("\n检测到炸弹、顺子、飞机 Biu~~ Biu~~  Bomb!!! Bomb!!!")
            return True
        return False

    def haveAnimation(self, waitTime=100):
        regions = [
            (960, 160, 960 + 20, 160 + 20),  # 下家动画位置
            (485, 160, 485 + 20, 160 + 20),  # 上家动画位置
            (700, 400, 700 + 20, 400 + 20),  # 自己上方动画位置
        ]
        img, _ = helper.Screenshot()
        lastImg = img
        for i in range(2):
            self.sleep(waitTime)
            img, _ = helper.Screenshot()
            for region in regions:
                if self.compareImage(img.crop(region), lastImg.crop(region)):
                    return True
            lastImg = img

        return False

    def compareImage(self, img1, img2):

        # 转换为灰度图
        gray1 = cv2.cvtColor(np.asarray(img1), cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(np.asarray(img2), cv2.COLOR_BGR2GRAY)

        # 使用结构相似性指数（SSIM）比较相似度
        ssim_index, _ = ssim(gray1, gray2, full=True)
        if ssim_index < 0.99:
            return True

        return False

    def real_to_env(self, cards):
        env_card = [RealCard2EnvCard[c] for c in cards]
        env_card.sort()
        return env_card

    def subtract_strings(self, str1, str2):
        result = ""
        for char1, char2 in zip(str1, str2):
            # 如果字符2在字符1中出现，则从字符1中删除该字符
            if char2 in str1:
                str1 = str1.replace(char2, '', 1)
        result = str1
        return result

    def compare_images(self, image1, image2, position):
        # 读取图像
        # 将图像转换为灰度图
        pic1 = cv2.cvtColor(np.asarray(image1), cv2.COLOR_RGB2BGR)
        pic2 = cv2.cvtColor(np.asarray(image2), cv2.COLOR_RGB2BGR)
        # 计算结构相似性指数
        cutPic = pic2[position[1]:position[1] + position[3], position[0]:position[0] + position[2]]
        result = gh.LocateOnImage(pic1, cutPic,
                                  region=(position[0] - 20, position[1] - 20, position[2] + 40, position[3] + 40))
        return result

    def cards_recorder(self, cards):
        for i in range(15):
            char = AllCards[i]
            num = cards.count(char)
            newItem = QTableWidgetItem(str(num))
            newItem.setTextAlignment(Qt.AlignHCenter)
            self.tableWidget.setItem(0, i, newItem)

    def recorder2zero(self):
        for i in range(15):
            newItem = QTableWidgetItem("0")
            newItem.setTextAlignment(Qt.AlignHCenter)
            self.tableWidget.setItem(0, i, newItem)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main = MyPyQT_Form()
    style_file = QFile("style.qss")
    stream = QTextStream(style_file)
    style_sheet = stream.readAll()
    main.setStyleSheet(style_sheet)
    main.show()
    sys.exit(app.exec_())