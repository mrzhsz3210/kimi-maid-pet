import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import unittest, time
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtTest import QTest
from pet import Pet,clamp_position

app=QApplication.instance() or QApplication([])
class Tests(unittest.TestCase):
    def setUp(self):self.pet=Pet();self.pet.show()
    def tearDown(self):
        self.pet.tick.stop();self.pet.bubble.close();self.pet.hide()
        self.pet.frames=[];self.pet.cache.clear();self.pet.pinned_frames.clear();self.pet.transition=None
        self.pet.deleteLater();app.processEvents()
    def test_all_assets_and_idle_weights(self):
        self.assertEqual(len(self.pet.variants),16)
        for item in self.pet.idles+self.pet.variants:self.assertEqual(len(self.pet.load(item)),({'17':120,'24':144,'knockback':144}.get(item['id'],96)))
        with patch('pet.random.choices',return_value=[self.pet.idles[1]]) as choice:
            self.pet.idle();self.assertEqual(choice.call_args.kwargs['weights'],[4,1])
    def test_click_disambiguation(self):
        with patch.object(self.pet,'single_click') as single:
            QTest.mouseClick(self.pet,Qt.MouseButton.LeftButton,pos=QPoint(160,160))
            QTest.qWait(80);QTest.mouseClick(self.pet,Qt.MouseButton.LeftButton,pos=QPoint(160,160))
            single.assert_called_once();self.pet.click_timer.stop()
        self.pet.last_click=None
        QTest.mouseClick(self.pet,Qt.MouseButton.LeftButton,pos=QPoint(160,160));QTest.qWait(300)
        self.assertEqual(self.pet.mode,'variant');self.assertTrue(self.pet.bubble.isVisible())
        self.assertLessEqual(self.pet.bubble_timer.remainingTime(),4000)
    def test_variant_return(self):
        self.pet.choose(self.pet.variants[0]);self.pet.started=time.monotonic()-4.01;self.pet.animate()
        self.assertEqual(self.pet.mode,'idle')
    def test_rapid_clicks_trigger_knockback(self):
        knockback=next(v for v in self.pet.variants if v['id']=='knockback')
        with patch.object(self.pet,'choose') as choose:
            for _ in range(3):self.pet.single_click()
            self.assertNotIn('knockback',[c.args[0]['id'] for c in choose.call_args_list])
            self.pet.single_click()
            self.assertEqual(choose.call_args.args[0]['id'],'knockback')
            self.pet.click_streak=0
    def test_deprecated_work_and_mood_idles(self):
        p=self.pet
        self.assertEqual({v['id'] for v in p.regular_work_animations()},{'work01','work02'})
        self.assertEqual(len(p.mood_idles),14)
        self.assertEqual(len(p.extra_idles),4)
        # 心情主导轴让对应站立待机进入 idle 候选
        p.mood.state['axes'].update(joy=8.0,anger=1.0,sorrow=1.0,fear=1.0)
        p.mood.state['updatedAt']=time.time()
        p.task_active=False;p.dock_edge=None;p.next_leisure_at=time.monotonic()+999
        with patch('pet.random.choices',return_value=[next(v for v in p.mood_idles if v['id']=='idle07')]) as choices:
            p.idle()
            self.assertEqual(p.current['id'],'idle07')
        p.mood.state['axes'].update(joy=p.mood.joy_baseline());p.mood.state['updatedAt']=time.time()
    def test_appearance_switch_reload(self):
        p=self.pet
        original=p.appearance
        try:
            p.set_appearance('白丝')
            self.assertEqual(p.appearance,'白丝')
            self.assertIn('白丝',str(p.asset_root()))
            self.assertEqual(p.manifest['character'],'Kimi娘')
            self.assertEqual(len(p.variants),16)
            key=str(p.asset_path(p.idles[0]))
            self.assertIn(key,p.pinned_frames)
        finally:
            p.set_appearance(original)
    def test_menu_contains_all_variants_and_exit(self):
        actions=[]
        def inspect():
            menu=app.activePopupWidget()
            actions.extend(a.text() for a in menu.actions() if not a.isSeparator());menu.close()
        QTimer.singleShot(100,inspect)
        QTest.mouseClick(self.pet,Qt.MouseButton.RightButton,pos=QPoint(160,160))
        self.assertEqual(actions,['隐藏桌宠','全屏时自动隐藏','打开对话模式','查看历史对话','对话框大小…','她此刻的心情…','编辑人设…','互动差分动画','工作差分动画','待机差分动画','移动差分','禁用自移动','外观（丝袜）','桌宠大小…','禁用音效','退出桌宠'])
        self.assertEqual(actions[-1],'退出桌宠')
    def test_drag_landing_and_click_suppression(self):
        from types import SimpleNamespace
        from PySide6.QtCore import QPointF
        press=SimpleNamespace(button=lambda:Qt.MouseButton.LeftButton,globalPosition=lambda:QPointF(200,200))
        move=SimpleNamespace(buttons=lambda:Qt.MouseButton.LeftButton,globalPosition=lambda:QPointF(240,230))
        self.pet.mousePressEvent(press);self.pet.mouseMoveEvent(move)
        self.assertEqual(self.pet.mode,'drag');self.assertEqual(self.pet.current['id'],'drag')
        self.pet.started=time.monotonic()-4.1;self.pet.animate();self.assertEqual(self.pet.mode,'drag')
        self.pet.mouseReleaseEvent(press)
        self.assertEqual(self.pet.mode,'landing');self.assertEqual(len(self.pet.frames),36)
        self.assertEqual(self.pet.current['durationMs'],1500);self.assertFalse(self.pet.click_timer.isActive())
        self.pet.started=time.monotonic()-1.6;self.pet.animate();self.assertEqual(self.pet.mode,'idle')
    def test_interaction_frames_survive_variant_eviction(self):
        for item in self.pet.variants[:3]:self.pet.load(item)
        with patch('pet.gzip.decompress',side_effect=AssertionError('drag must not decode on mouse movement')):
            drag=self.pet.manifest['dragAnimation'];landing=self.pet.manifest['landingAnimation']
            self.assertIs(self.pet.load(drag),self.pet.pinned_frames[str(self.pet.asset_path(drag))])
            self.assertEqual(len(self.pet.load(landing)),36)
    def test_variant_cache_bounded_and_idle_return_is_warm(self):
        for item in self.pet.variants:
            self.pet.choose(item)
            self.assertLessEqual(len(self.pet.cache),2)
            self.pet.started=time.monotonic()-item['durationMs']/1000-.1
            with patch('pet.gzip.decompress',side_effect=AssertionError('idle should stay warm')):
                self.pet.animate()
                self.assertEqual(self.pet.mode,'idle')
class BoundaryTests(unittest.TestCase):
    def test_edges_and_corners(self):
        from PySide6.QtCore import QRect,QSize
        area=QRect(0,0,1920,1040);size=QSize(256,256)
        for point in [QPoint(-500,-500),QPoint(3000,-500),QPoint(-500,3000),QPoint(3000,3000),QPoint(800,300)]:
            bounded=clamp_position(point,size,area)
            self.assertTrue(area.contains(QRect(bounded,size)))
        self.assertEqual(clamp_position(QPoint(3000,3000),size,area),QPoint(1664,784))
    def test_negative_monitor_coordinates(self):
        from PySide6.QtCore import QRect,QSize
        area=QRect(-1920,-200,1920,1040);size=QSize(256,256)
        self.assertEqual(clamp_position(QPoint(-4000,-1000),size,area),QPoint(-1920,-200))
        self.assertTrue(area.contains(QRect(clamp_position(QPoint(20,1000),size,area),size)))

if __name__=='__main__':unittest.main()
