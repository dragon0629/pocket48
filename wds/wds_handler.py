# -*- coding:utf-8 -*-

import json
import sys

import requests
from bs4 import BeautifulSoup
from qqbot.utf8logger import INFO, ERROR, DEBUG
import time
import re

from qqhandler import QQHandler

reload(sys)
sys.setdefaultencoding('utf8')


class WDS:
    def __init__(self, link, title, post_id, pro_id, need_display_rank=False):
        self.link = link
        self.title = title
        self.post_id = post_id
        self.pro_id = pro_id
        self.need_display_rank = need_display_rank


class WDSHandler:
    def __init__(self, wds_notify_groups, wds_array):
        # self.comment_id_queue = []
        self.session = requests.session()
        self.wds_notify_groups = wds_notify_groups
        self.wds_array = wds_array

        self.wds_queue_map = {}
        self.comment_id_queues = []

    def init_comment_queues(self):
        """
        初始化回复队列
        :param moxi_id:
        :param pro_id:
        :return:
        """
        try:
            self.comment_id_queues = []
            for i in range(len(self.wds_array)):
                self.comment_id_queues.append([])

            for i in range(len(self.wds_array)):
                queue = self.comment_id_queues[i]
                r = self.monitor_wds_comment(self.wds_array[i])

                # for reply in r['des']:
                #     reply_id = reply['reply_id']
                #     queue.append(reply_id)

                soup = BeautifulSoup(r, 'lxml')
                comment_list = soup.findAll(name='li')
                for comment in comment_list:
                    comment_id = comment.find(class_='add-jubao').get('to_comid')
                    queue.append(comment_id)

                self.wds_queue_map[self.wds_array[i]] = queue
        except Exception as e:
            ERROR('初始化微打赏评论队列失败')
            ERROR(e)

    def wds_header(self):
        """
        微打赏header信息
        """
        header = {
            # 'Host': 'wds.modian.com',
            # 'Accept': 'application/json',
            # 'Accept-Encoding': 'gzip,deflate,br',
            # 'Connection': 'keep-alive',
            # 'Content-Length': '37',
            # 'Content-Type': 'application/x-www-form-urlencoded',
            # 'Origin': 'https://wds.modian.com',
            # 'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.104 Safari/537.36 Core/1.53.3408.400 QQBrowser/9.6.12028.40',
        }
        return header

    def monitor_wds_comment(self, wds, page_num=1):
        """
        获取微打赏项目下的评论信息
        :return:
        """
        jizi_url = 'https://wds.modian.com/ajax/comment_list'
        params = {
            'pageNum': page_num,
            'post_id': wds.post_id,
            'pro_id': wds.pro_id
        }
        try:
            # 注意，这里的param不用转换成json了，因为参数格式为x-www-form-urlencoded
            r = self.session.post(jizi_url, params, headers=self.wds_header())
        except Exception as e:
            ERROR('获取微打赏评论失败')
            ERROR(e)
        # DEBUG('response: %s', r.text)
        # print r.text
        r_json = r.json()
        if int(r_json['status']) != 0:
            ERROR('获取失败!')
        return r_json['data']['html']

    def parse_wds_comment2(self, r, wds):
        """
        对评论进行处理（微打赏接口变更，r变为html）
        :param r:
        :param wds:
        :return:
        """
        soup = BeautifulSoup(r, 'lxml')
        # print soup.prettify()
        comment_list = soup.findAll(name='li')
        support_num, current, target = self.get_current_and_target(wds)
        project_info = '当前进度: %s元, 目标金额: %s元\n当前集资人数: %s\n' % (current, target, support_num)

        soup2 = BeautifulSoup(self.get_wds_rank(wds, page_size=int(support_num)), 'lxml')
        # print soup2.prettify()
        wds_rank_list = soup2.findAll(name='li')

        for comment in comment_list:
            msg = ''
            comment_id = comment.find(class_='add-jubao').get('to_comid')
            # print comment_id

            comment_id_queue = self.wds_queue_map[wds]
            if comment_id in comment_id_queue:
                continue
            comment_id_queue.append(comment_id)

            nickname = comment.find(class_='nick').string
            nick_sup = comment.find(class_='nick_sup').string
            user_id = comment.find(class_='add-jubao').get('to_user')

            msg = '感谢%s%s, 灰灰爱你哟~\n' % (nickname, nick_sup)

            rank_msg = ''
            for rank in wds_rank_list:
                user_a = rank.a['href']
                uid = re.findall(r"\d+\.?\d*", user_a)[0]

                if uid == user_id:
                    cur_rank = rank.find(class_='suport_ran').string
                    total_amount = rank.find(class_='money').string
                    total_amount = re.findall(r"\d+\.?\d*", total_amount)[0]

                    if wds.need_display_rank is True:
                        rank_msg = "当前累计集资%s元，当前排名: %s\n" % (total_amount, cur_rank)
                    else:
                        rank_msg = "当前累计集资%s元\n" % total_amount
                    break
            if rank_msg and len(rank_msg) > 0:
                msg += rank_msg

            if msg and len(msg) > 0:
                msg += project_info
                msg += '集资项目: %s\n链接: %s' % (wds.title, wds.link)
                QQHandler.send_to_groups(self.wds_notify_groups, msg)
                INFO('wds_message: %s', msg)
                DEBUG('集资评论队列: %d', len(comment_id_queue))

            time.sleep(3)

    # def parse_wds_comment(self, r, wds):
    #     """
    #     对评论进行处理
    #     :param wds:
    #     :param r:
    #     :return:
    #     """
    #     des = r['des']
    #     print des
    #     # DEBUG(json.dumps(des))
    #     DEBUG('LENGTH OF DES: %d', len(des))
    #
    #     support_num, current, target = self.get_current_and_target(wds)
    #     project_info = '当前进度: %s元, 目标金额: %s元\n当前集资人数: %s\n' % (current, target, support_num)
    #     wds_rank_list = self.get_wds_rank(wds, page_size=int(support_num))['data']
    #
    #     for reply in des:
    #         msg = ''
    #         reply_id = reply['reply_id']
    #
    #         comment_id_queue = self.wds_queue_map[wds]
    #         if reply_id in comment_id_queue:
    #             continue
    #         comment_id_queue.append(reply_id)
    #
    #         pay_amount = reply['pay_amount']
    #         if pay_amount == '':  # 去除单纯的评论
    #             continue
    #
    #         user_info = reply['c_userinfo']
    #         user_id = user_info['nickname']
    #         uid = user_info['id']
    #
    #         cur_rank = 1
    #
    #         sub_msg = '感谢 %s 集资%s元, 灰灰爱你哟~\n' % (user_id, pay_amount)
    #         rank_msg = ''
    #         for rank in wds_rank_list:
    #             if uid == rank["user_id"]:
    #                 total_back_amount = rank["total_back_amount"]
    #                 if wds.need_display_rank is True:
    #                     rank_msg = "当前累计集资%.2f元，当前排名: %d\n" % (total_back_amount, cur_rank)
    #                 else:
    #                     rank_msg = "当前累计集资%.2f元\n" % total_back_amount
    #                 break
    #             cur_rank += 1
    #
    #         if rank_msg and len(rank_msg) > 0:
    #             sub_msg += rank_msg
    #         INFO(sub_msg)
    #         msg += sub_msg
    #
    #         if msg and len(msg) > 0:
    #             msg += project_info
    #             msg += '集资项目: %s\n链接: %s' % (wds.title, wds.link)
    #             QQHandler.send_to_groups(self.wds_notify_groups, msg)
    #             INFO('wds_message: %s', msg)
    #             DEBUG('集资评论队列: %d', len(comment_id_queue))
    #
    #         time.sleep(3)

    def get_wds_rank(self, wds, type0=1, page=1, page_size=50):
        """
        获取微打赏聚聚榜
        :param wds:
        :param pro_id:
        :param type0:
        :param page:
        :param page_size:
        :return:
        """
        jizi_url = 'https://wds.modian.com/ajax/backer_ranking_list'
        params = {
            'pro_id': wds.pro_id,
            'type': type0,
            'page': page,
            'page_size': page_size
        }
        try:
            # 注意，这里的param不用转换成json了，因为参数格式为x-www-form-urlencoded
            r = self.session.post(jizi_url, params, headers=self.wds_header())
        except Exception as e:
            ERROR('获取微打赏评论失败')
            ERROR(e)
        r_json = r.json()
        # DEBUG('response: %s', r.text)
        if int(r_json['status']) != 0:
            ERROR('获取失败!')
        return r_json['data']['html']

    def get_current_and_target(self, wds):
        """
        获取当前进度和总额
        :return:
        """
        header = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip,deflate,sdch,br',
            'Accept-Language': 'zh-CN,zh;q=0.8',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Host': 'wds.modian.com',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.104 Safari/537.36 Core/1.53.3408.400 QQBrowser/9.6.12028.400'
        }
        r = requests.get(wds.link, headers=header)
        soup = BeautifulSoup(r.text, 'lxml')
        # print soup.prettify()

        project_info = soup.find_all(class_="project-info")[0]
        support_num = project_info.find_all(class_="b")[0].find_all(name="span")[0].contents[0].strip()
        DEBUG('当前集资人数: %s', support_num)

        current = project_info.find_all(class_="current")[0].find_all(name="span")[1].contents[1].strip()
        DEBUG('当前进度: %s元', current)
        target = project_info.find_all(class_="target")[0].find_all(name="span")[1].contents[1].strip()
        DEBUG('目标金额: %s元', target)

        return support_num, current, target


if __name__ == '__main__':
    wds1 = WDS('https://wds.modian.com/show_weidashang_pro/7974', '冯晓菲应援会10月日常集资企划', 17011, 7974, False)
    wds2 = WDS('https://wds.modian.com/show_weidashang_pro/8303', '《暴走少女》冯晓菲应援会2017年第四届金曲大赏集资', 17526, 8303, False)
    wds_array = [wds1, wds2]
    handler = WDSHandler([], [])
    handler.wds_array = wds_array

    handler.init_comment_queues()

    r1 = handler.monitor_wds_comment(wds1)
    handler.parse_wds_comment2(r1, wds1)
    # handler.get_wds_rank(wds1)

    # handler.monitor_wds_comment(wds2)
    # handler.get_wds_rank(wds2)
