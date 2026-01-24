from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, BooleanProperty, DictProperty, NumericProperty, ObjectProperty
from kivy.clock import Clock, mainthread
from kivy.utils import platform, get_color_from_hex
from kivy.metrics import dp
from kivy.animation import Animation
from kivy.uix.relativelayout import RelativeLayout
from datetime import datetime, timedelta
import concurrent.futures
import requests
import json
import os
import time
import sqlite3
from collections import OrderedDict

from kivy.core.clipboard import Clipboard 
from kivymd.app import MDApp
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.list import OneLineListItem, TwoLineListItem, OneLineIconListItem
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import OneLineAvatarIconListItem
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.card import MDCard
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout

# إعدادات الشاشة للحاسوب
if platform not in ("android", "ios"):
    Window.size = (400, 800)

# استيراد المكتبات اللازمة للأندرويد
if platform == 'android':
    from android.permissions import request_permissions, Permission
    from android import api_version
    from jnius import autoclass, cast
    
    Environment = autoclass('android.os.Environment')
    Intent = autoclass('android.content.Intent')
    Settings = autoclass('android.provider.Settings')
    Uri = autoclass('android.net.Uri')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Context = autoclass('android.content.Context')
    File = autoclass('java.io.File')


class SQLiteStorage:
    def __init__(self, db_name='football_data.db'):
        self.db_path = self._get_external_db_path(db_name)
        self._ensure_db_directory()
        self.init_database()
        
        print(f"📁 SQLite DB Path: {self.db_path}")
        if platform == 'android':
            print(f"📁 يمكنك الوصول للملف من: /storage/emulated/0/FootballAppDB/")
        
        self._show_db_location_info()

    def _get_external_db_path(self, db_name):
        """تحديد مسار قاعدة البيانات"""
        if platform == 'android':
            try:
                base_path = "/storage/emulated/0"
                app_folder = os.path.join(base_path, "FootballAppDB")
                
                try:
                    os.makedirs(app_folder, exist_ok=True)
                    print(f"✅ تم إنشاء/التأكد من مجلد: {app_folder}")
                except Exception as e:
                    print(f"⚠️ قد يكون هناك مشكلة في الإذن: {e}")
                
                try:
                    java_file = File(app_folder)
                    if java_file.canWrite():
                        print("✅ Java API: يمكن الكتابة في المجلد")
                    else:
                        print("⚠️ Java API: لا يمكن الكتابة في المجلد")
                except:
                    pass
                
                return os.path.join(app_folder, db_name)
                
            except Exception as e:
                print(f"⚠️ فشل المسار الخارجي: {e}")
                return self._get_fallback_path(db_name)
        else:
            path = os.path.join(os.path.expanduser("~"), "FootballAppDB")
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            return os.path.join(path, db_name)

    def _request_manage_storage_permission(self):
        """طلب إذن MANAGE_EXTERNAL_STORAGE"""
        if platform == 'android':
            try:
                if api_version >= 30:
                    if not Environment.isExternalStorageManager():
                        try:
                            mActivity = PythonActivity.mActivity
                            intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
                            uri = Uri.parse("package:" + mActivity.getPackageName())
                            intent.setData(uri)
                            mActivity.startActivity(intent)
                            print("ℹ️ تم فتح الإعدادات لتفعيل الوصول للملفات")
                            
                            Clock.schedule_once(lambda dt: self._show_permission_guide(), 2)
                        except Exception as e:
                            print(f"⚠️ خطأ في فتح إعدادات الوصول: {e}")
                            intent = Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION)
                            PythonActivity.mActivity.startActivity(intent)
                else:
                    permissions = [Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE]
                    
                    def callback(permissions, results):
                        if all(results):
                            print("✅ تم منح أذونات التخزين")
                        else:
                            print("⚠️ تم رفض بعض الأذونات")
                    
                    request_permissions(permissions, callback)
            except Exception as e:
                print(f"⚠️ خطأ في طلب الإذن: {e}")

    def _show_permission_guide(self):
        """عرض رسالة توجيهية"""
        try:
            app = MDApp.get_running_app()
            if app:
                app.show_snackbar(
                    "🔧 الرجاء تفعيل 'الوصول لجميع الملفات' في الإعدادات\n"
                    "ثم أعد تشغيل التطبيق", 
                    duration=5
                )
        except:
            pass

    def _get_fallback_path(self, db_name):
        """مسار احتياطي داخل مجلد التطبيق الخاص"""
        if platform == 'android':
            try:
                context = PythonActivity.mActivity.getApplicationContext()
                files_dir = context.getFilesDir()
                return os.path.join(str(files_dir.toString()), db_name)
            except:
                return db_name
        return db_name

    def _ensure_db_directory(self):
        """إنشاء المجلد في ذاكرة الهاتف"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                db_dir = os.path.dirname(self.db_path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                    print(f"✅ تم إنشاء المجلد: {db_dir}")
                
                test_file = os.path.join(db_dir, "test_write.tmp")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                print("✅ اختبار الكتابة ناجح")
                return
                
            except PermissionError:
                print(f"⚠️ محاولة {attempt+1}: لا يوجد إذن كتابة")
                if attempt == 0:
                    Clock.schedule_once(lambda dt: self._request_manage_storage_permission(), 1)
                time.sleep(1)
            except Exception as e:
                print(f"⚠️ خطأ في إنشاء المجلد: {e}")
                break

    def _show_db_location_info(self):
        """عرض معلومات موقع قاعدة البيانات"""
        print(f"📍 موقع قاعدة البيانات:")
        print(f"   {self.db_path}")
        print(f"📍 للوصول للملف:")
        print(f"   1. افتح 'مدير الملفات'")
        print(f"   2. اذهب إلى '/storage/emulated/0/FootballAppDB/'")
        print(f"   3. ستجد الملف 'football_data.db'")

    def get_connection(self):
        """الحصول على اتصال بقاعدة البيانات"""
        return sqlite3.connect(self.db_path)

    def init_database(self):
        """تهيئة قاعدة البيانات وإنشاء الجداول"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # جدول المباريات المفضلة
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY,
                    match_data TEXT
                )
            """)

            # جدول المباريات المخفية
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hidden_matches (
                    id INTEGER PRIMARY KEY,
                    match_data TEXT
                )
            """)

            # جدول الدوريات المفضلة
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorite_leagues (
                    id INTEGER PRIMARY KEY,
                    league_name TEXT,
                    league_id INTEGER UNIQUE
                )
            """)

            # جدول الدوريات المحددة
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS selected_leagues (
                    id INTEGER PRIMARY KEY,
                    league_name TEXT,
                    league_id INTEGER UNIQUE
                )
            """)

            # جدول إعدادات الفلتر
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS filter_settings (
                    id INTEGER PRIMARY KEY,
                    setting_name TEXT UNIQUE,
                    setting_value TEXT
                )
            """)

            # جدول كاش المباريات المجدولة
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_matches_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_date TEXT,
                    league_id INTEGER,
                    match_data TEXT,
                    UNIQUE(match_date, league_id)
                )
            """)

            # جدول الترتيب الحالي للدوريات
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS league_standings_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    league_id INTEGER,
                    season INTEGER,
                    standings_data TEXT,
                    UNIQUE(league_id, season)
                )
            """)

            # جدول ترتيب الموسم الماضي
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS last_season_standings_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    league_id INTEGER,
                    season INTEGER,
                    standings_data TEXT,
                    UNIQUE(league_id, season)
                )
            """)

            # ⭐⭐ تحديث: جدول كاش أهداف الفرق (فقط للمباريات المجدولة)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_teams_goals_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    league_id INTEGER,
                    season INTEGER,
                    match_date TEXT,
                    goals_data TEXT,  -- بيانات JSON لفرق المباريات المجدولة فقط
                    last_updated TEXT,
                    UNIQUE(league_id, season, match_date)
                )
            """)

            conn.commit()
            conn.close()
            print("✅ Database initialized successfully with scheduled teams goals cache")

        except Exception as e:
            print(f"❌ DB init error: {e}")

    def get_last_season_cache_by_team(self, team_id, season):
        """جلب بيانات الفريق من كاش الموسم الماضي"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT standings_data FROM last_season_standings_cache
                WHERE season = ?
            ''', (season,))
            
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                if row[0]:
                    try:
                        league_data = json.loads(row[0])
                        for team_data in league_data:
                            if team_data.get('team_id') == team_id:
                                return team_data
                    except:
                        continue
            
            return None
        except Exception as e:
            print(f"Error getting last season cache by team: {e}")
            return None

    def save_league_standings_to_cache(self, league_id, season, standings_data):
        """حفظ ترتيب الدوري في الكاش مع التحقق من التكرار"""
        try:
            # التحقق من وجود البيانات أولاً قبل الحفظ
            existing_data = self.load_league_standings_from_cache(league_id, season)
            
            if existing_data:
                # مقارنة البيانات لتجنب الحفظ المكرر
                existing_json = json.dumps(existing_data, sort_keys=True)
                new_json = json.dumps(standings_data, sort_keys=True)
                
                if existing_json == new_json:
                    print(f"ℹ️ بيانات الدوري {league_id} للموسم {season} موجودة بالفعل في الكاش")
                    return True  # البيانات موجودة بالفعل، لا حاجة للحفظ
            
            # إذا لم تكن موجودة أو مختلفة، نقوم بالحفظ
            conn = self.get_connection()
            cursor = conn.cursor()
            
            json_data = json.dumps(standings_data)
            
            cursor.execute('''
                INSERT OR REPLACE INTO league_standings_cache 
                (league_id, season, standings_data)
                VALUES (?, ?, ?)
            ''', (league_id, season, json_data))
            
            conn.commit()
            conn.close()
            print(f"✅ تم حفظ ترتيب الدوري {league_id} للموسم {season}")
            return True
        except Exception as e:
            print(f"❌ خطأ في حفظ كاش الترتيب: {e}")
            return False

    def load_league_standings_from_cache(self, league_id, season):
        """تحميل ترتيب الدوري من الكاش"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT standings_data FROM league_standings_cache
                WHERE league_id = ? AND season = ?
            ''', (league_id, season))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                standings_data = json.loads(row[0])
                print(f"✅ تم تحميل ترتيب الدوري {league_id} للموسم {season} من الكاش")
                return standings_data
            
            return None
        except Exception as e:
            print(f"❌ خطأ في تحميل كاش الترتيب: {e}")
            return None

    def save_last_season_standings_to_cache(self, league_id, season, standings_data):
        """حفظ ترتيب الموسم الماضي مع التحقق من التكرار"""
        try:
            # التحقق أولاً من وجود البيانات في الكاش
            existing_data = self.load_last_season_standings_from_cache(league_id, season)
            
            if existing_data:
                # مقارنة البيانات لتجنب الحفظ المكرر
                existing_json = json.dumps(existing_data, sort_keys=True)
                new_json = json.dumps(standings_data, sort_keys=True)
                
                if existing_json == new_json:
                    print(f"ℹ️ بيانات الموسم الماضي {league_id} للموسم {season} موجودة بالفعل في الكاش")
                    return True  # البيانات موجودة بالفعل، لا حاجة للحفظ
            
            # إذا لم تكن موجودة أو مختلفة، نقوم بالحفظ
            conn = self.get_connection()
            cursor = conn.cursor()
            
            json_data = json.dumps(standings_data)
            
            cursor.execute('''
                INSERT OR REPLACE INTO last_season_standings_cache 
                (league_id, season, standings_data)
                VALUES (?, ?, ?)
            ''', (league_id, season, json_data))
            
            conn.commit()
            conn.close()
            print(f"✅ تم حفظ ترتيب الموسم الماضي للدوري {league_id} للموسم {season}")
            return True
        except Exception as e:
            print(f"❌ خطأ في حفظ كاش الموسم الماضي: {e}")
            return False

    def load_last_season_standings_from_cache(self, league_id, season):
        """تحميل ترتيب الموسم الماضي"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT standings_data FROM last_season_standings_cache
                WHERE league_id = ? AND season = ?
            ''', (league_id, season))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                standings_data = json.loads(row[0])
                print(f"✅ تم تحميل ترتيب الموسم الماضي للدوري {league_id}")
                return standings_data
            
            return None
        except Exception as e:
            print(f"❌ خطأ في تحميل كاش الموسم الماضي: {e}")
            return None

    def save_scheduled_matches_to_cache(self, match_date, league_id, match_data):
        """حفظ المباريات المجدولة في الكاش مع التحقق من التكرار"""
        try:
            # التحقق أولاً من وجود البيانات في الكاش
            existing_data = self.load_scheduled_matches_from_cache(match_date, league_id)
            
            if existing_data:
                # مقارنة البيانات لتجنب الحفظ المكرر
                existing_json = json.dumps(existing_data, sort_keys=True)
                new_json = json.dumps(match_data, sort_keys=True)
                
                if existing_json == new_json:
                    print(f"ℹ️ المباريات المجدولة للدوري {league_id} بتاريخ {match_date} موجودة بالفعل في الكاش")
                    return True  # البيانات موجودة بالفعل، لا حاجة للحفظ
            
            # إذا لم تكن موجودة أو مختلفة، نقوم بالحفظ
            conn = self.get_connection()
            cursor = conn.cursor()
            
            json_data = json.dumps(match_data)
            
            cursor.execute('''
                INSERT OR REPLACE INTO scheduled_matches_cache 
                (match_date, league_id, match_data)
                VALUES (?, ?, ?)
            ''', (match_date, league_id, json_data))
            
            conn.commit()
            conn.close()
            print(f"✅ تم حفظ {len(match_data)} مباراة في الكاش للتاريخ {match_date}")
            return True
        except Exception as e:
            print(f"❌ خطأ في حفظ الكاش: {e}")
            return False

    def load_scheduled_matches_from_cache(self, match_date, league_id):
        """تحميل المباريات المجدولة من الكاش باستخدام set لتحسين الأداء"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT match_data FROM scheduled_matches_cache
                WHERE match_date = ? AND league_id = ?
            ''', (match_date, league_id))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                match_data = json.loads(row[0])
                print(f"✅ تم تحميل {len(match_data)} مباراة من الكاش")
                
                # استخدام set لإزالة التكرارات السريعة
                seen_ids = set()
                unique_matches = []
                
                for match in match_data:
                    match_id = match.get('id')
                    if match_id and match_id not in seen_ids:
                        seen_ids.add(match_id)
                        unique_matches.append(match)
                
                if len(unique_matches) < len(match_data):
                    print(f"✅ تمت إزالة {len(match_data) - len(unique_matches)} مباراة مكررة باستخدام set")
                
                return unique_matches
            
            return None
        except Exception as e:
            print(f"❌ خطأ في تحميل الكاش: {e}")
            return None

    # ⭐⭐ دوال الكاش الجديد للأهداف (للمباريات المجدولة فقط)
    def save_scheduled_teams_goals_cache(self, league_id, season, match_date, goals_data):
        """حفظ بيانات الأهداف للفرق المجدولة فقط مع التحقق من التكرار"""
        try:
            # التحقق أولاً من وجود البيانات في الكاش
            existing_data = self.load_scheduled_teams_goals_cache(league_id, season, match_date)
            
            if existing_data:
                # مقارنة البيانات لتجنب الحفظ المكرر
                existing_json = json.dumps(existing_data, sort_keys=True)
                new_json = json.dumps(goals_data, sort_keys=True)
                
                if existing_json == new_json:
                    print(f"ℹ️ بيانات أهداف الفرق للدوري {league_id} بتاريخ {match_date} موجودة بالفعل في الكاش")
                    return True  # البيانات موجودة بالفعل، لا حاجة للحفظ
            
            # إذا لم تكن موجودة أو مختلفة، نقوم بالحفظ
            conn = self.get_connection()
            cursor = conn.cursor()
            
            last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            json_data = json.dumps(goals_data)
            
            cursor.execute('''
                INSERT OR REPLACE INTO scheduled_teams_goals_cache 
                (league_id, season, match_date, goals_data, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (league_id, season, match_date, json_data, last_updated))
            
            conn.commit()
            conn.close()
            print(f"✅ تم حفظ كاش الأهداف لـ {len(goals_data)} فريق مجدول ({league_id} - {match_date})")
            return True
        except Exception as e:
            print(f"❌ خطأ في حفظ كاش الأهداف للفرق المجدولة: {e}")
            return False

    def load_scheduled_teams_goals_cache(self, league_id, season, match_date):
        """تحميل بيانات الأهداف للفرق المجدولة"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT goals_data FROM scheduled_teams_goals_cache
                WHERE league_id = ? AND season = ? AND match_date = ?
            ''', (league_id, season, match_date))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                goals_data = json.loads(row[0])
                print(f"✅ تم تحميل كاش الأهداف لـ {len(goals_data)} فريق مجدول")
                return goals_data
            
            return None
        except Exception as e:
            print(f"❌ خطأ في تحميل كاش الأهداف للفرق المجدولة: {e}")
            return None

    def update_scheduled_teams_goals_cache(self, league_id, season, match_date, new_data):
        """تحديث كاش الأهداف ببيانات جديدة مع التحقق من التكرار"""
        try:
            # جلب البيانات الحالية
            existing_data = self.load_scheduled_teams_goals_cache(league_id, season, match_date) or {}
            
            # التحقق مما إذا كانت البيانات الجديدة موجودة بالفعل
            needs_update = False
            for team_key, team_data in new_data.items():
                if team_key not in existing_data:
                    needs_update = True
                    break
                else:
                    # مقارنة البيانات الحالية مع الجديدة
                    existing_json = json.dumps(existing_data[team_key], sort_keys=True)
                    new_json = json.dumps(team_data, sort_keys=True)
                    if existing_json != new_json:
                        needs_update = True
                        break
            
            if not needs_update:
                print(f"ℹ️ جميع البيانات الجديدة موجودة بالفعل في الكاش")
                return True
            
            # دمج البيانات الجديدة مع الحالية
            existing_data.update(new_data)
            
            # حفظ البيانات المدمجة
            success = self.save_scheduled_teams_goals_cache(league_id, season, match_date, existing_data)
            
            if success:
                print(f"✅ تم تحديث كاش الأهداف بـ {len(new_data)} فريق جديد")
            
            return success
            
        except Exception as e:
            print(f"❌ خطأ في تحديث كاش الأهداف: {e}")
            return False

    # دوال المباريات المفضلة
    def load_favorites(self):
        """تحميل المباريات المفضلة باستخدام set لتحسين الأداء"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT match_data FROM favorites')
            rows = cursor.fetchall()
            conn.close()
            
            favorites = []
            seen_ids = set()  # استخدام set للكشف عن التكرارات
            
            for row in rows:
                try:
                    match_data = json.loads(row[0])
                    match_id = match_data.get('id')
                    
                    if match_id and match_id not in seen_ids:
                        seen_ids.add(match_id)
                        favorites.append(match_data)
                except Exception as e:
                    print(f"❌ خطأ في تحميل مباراة من المفضلة: {e}")
            
            print(f"✅ تم تحميل {len(favorites)} مباراة من المفضلة (مجموعة فريدة)")
            return favorites
        except Exception as e:
            print(f"❌ خطأ في تحميل المفضلة: {e}")
            return []

    def save_favorites(self, favorites):
        """حفظ المباريات المفضلة"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM favorites')
            
            for match in favorites:
                try:
                    match_data = json.dumps(match)
                    cursor.execute('INSERT INTO favorites (match_data) VALUES (?)', (match_data,))
                except Exception as e:
                    print(f"❌ خطأ في حفظ مباراة في المفضلة: {e}")
            
            conn.commit()
            conn.close()
            print(f"✅ تم حفظ {len(favorites)} مباراة في المفضلة")
        except Exception as e:
            print(f"❌ خطأ في حفظ المفضلة: {e}")

    # دوال المباريات المخفية
    def load_hidden_matches(self):
        """تحميل المباريات المخفية باستخدام set لتحسين الأداء"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT match_data FROM hidden_matches')
            rows = cursor.fetchall()
            conn.close()
            
            hidden_matches = []
            seen_ids = set()  # استخدام set للكشف عن التكرارات
            
            for row in rows:
                try:
                    match_data = json.loads(row[0])
                    match_id = match_data.get('id')
                    
                    if match_id and match_id not in seen_ids:
                        seen_ids.add(match_id)
                        hidden_matches.append(match_data)
                except Exception as e:
                    print(f"❌ خطأ في تحميل مباراة مخفية: {e}")
            
            print(f"✅ تم تحميل {len(hidden_matches)} مباراة مخفية (مجموعة فريدة)")
            return hidden_matches
        except Exception as e:
            print(f"❌ خطأ في تحميل المباريات المخفية: {e}")
            return []

    def save_hidden_matches(self, hidden_matches):
        """حفظ المباريات المخفية"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM hidden_matches')
            
            for match in hidden_matches:
                try:
                    match_data = json.dumps(match)
                    cursor.execute('INSERT INTO hidden_matches (match_data) VALUES (?)', (match_data,))
                except:
                    pass
            
            conn.commit()
            conn.close()
        except:
            pass

    # دوال الدوريات المفضلة
    def load_favorite_leagues(self):
        """تحميل الدوريات المفضلة"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT league_name, league_id FROM favorite_leagues')
            rows = cursor.fetchall()
            conn.close()
            
            favorite_leagues = []
            for row in rows:
                favorite_leagues.append({'name': row[0], 'id': row[1]})
            return favorite_leagues
        except:
            return []

    def save_favorite_leagues(self, favorite_leagues):
        """حفظ الدوريات المفضلة"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM favorite_leagues')
            
            for league in favorite_leagues:
                try:
                    cursor.execute('INSERT INTO favorite_leagues (league_name, league_id) VALUES (?, ?)',
                                 (league['name'], league['id']))
                except:
                    pass
            
            conn.commit()
            conn.close()
        except:
            pass

    # دوال الدوريات المحددة
    def load_league_selection(self):
        """تحميل الدوريات المحددة"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT league_name, league_id FROM selected_leagues')
            rows = cursor.fetchall()
            conn.close()
            
            selected_leagues = []
            for row in rows:
                selected_leagues.append({'name': row[0], 'id': row[1]})
            return selected_leagues
        except:
            return []

    def save_league_selection(self, selected_leagues):
        """حفظ الدوريات المحددة"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM selected_leagues')
            
            for league in selected_leagues:
                try:
                    cursor.execute('INSERT INTO selected_leagues (league_name, league_id) VALUES (?, ?)',
                                 (league['name'], league['id']))
                except:
                    pass
            
            conn.commit()
            conn.close()
        except:
            pass

    # دوال إعدادات الفلتر
    def load_filter_state(self, setting_name):
        """تحميل حالة الفلتر"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT setting_value FROM filter_settings WHERE setting_name = ?', (setting_name,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return row[0] == 'True'
            return False
        except:
            return False

    def save_filter_state(self, setting_name, state):
        """حفظ حالة الفلتر"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO filter_settings (setting_name, setting_value)
                VALUES (?, ?)
            ''', (setting_name, str(state)))
            
            conn.commit()
            conn.close()
        except:
            pass

    def check_cache_exists(self, match_date, league_id):
        """التحقق من وجود بيانات في الكاش"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 1 FROM scheduled_matches_cache 
                WHERE match_date = ? AND league_id = ? LIMIT 1
            ''', (match_date, league_id))
            
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except:
            return False

    def clear_specific_cache(self, tables=None):
        """مسح جداول كاش محددة فقط"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cleared_tables = []
            
            if tables is None or 'scheduled_matches_cache' in tables:
                cursor.execute('DELETE FROM scheduled_matches_cache')
                cleared_tables.append('scheduled_matches_cache')
                print(f"✅ تم مسح جدول scheduled_matches_cache")
            
            if tables is None or 'league_standings_cache' in tables:
                cursor.execute('DELETE FROM league_standings_cache')
                cleared_tables.append('league_standings_cache')
                print(f"✅ تم مسح جدول league_standings_cache")
            
            if tables is None or 'scheduled_teams_goals_cache' in tables:
                cursor.execute('DELETE FROM scheduled_teams_goals_cache')
                cleared_tables.append('scheduled_teams_goals_cache')
                print(f"✅ تم مسح جدول scheduled_teams_goals_cache")
            
            conn.commit()
            conn.close()
            
            print(f"✅ تم مسح {len(cleared_tables)} جدول من الكاش")
            return True, cleared_tables
            
        except Exception as e:
            print(f"❌ خطأ في مسح الكاش: {e}")
            return False, []

    def delete_match_from_scheduled_cache(self, match_id, league_id, match_date):
        """حذف مباراة محددة من scheduled_matches_cache"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT match_data FROM scheduled_matches_cache
                WHERE match_date = ? AND league_id = ?
            ''', (match_date, league_id))
            
            row = cursor.fetchone()
            if row:
                match_data = json.loads(row[0])
                
                filtered_matches = [
                    match for match in match_data 
                    if match.get('id') != match_id
                ]
                
                if len(filtered_matches) == 0:
                    cursor.execute('''
                        DELETE FROM scheduled_matches_cache
                        WHERE match_date = ? AND league_id = ?
                    ''', (match_date, league_id))
                else:
                    json_data = json.dumps(filtered_matches)
                    cursor.execute('''
                        UPDATE scheduled_matches_cache
                        SET match_data = ?
                        WHERE match_date = ? AND league_id = ?
                    ''', (json_data, match_date, league_id))
                
                conn.commit()
                conn.close()
                print(f"✅ تم حذف المباراة {match_id} من كاش المباريات المجدولة")
                return True
            else:
                conn.close()
                return False
                
        except Exception as e:
            print(f"❌ خطأ في حذف المباراة من الكاش: {e}")
            return False


class CalendarHeader(MDBoxLayout):
    selected_date = StringProperty("")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = MDApp.get_running_app()
        self.current_date = datetime.now().date()
        self.min_date = datetime.now().date() - timedelta(days=30)
        self.max_date = datetime.now().date() + timedelta(days=365)
        self.update_display()
    
    def update_display(self):
        today = datetime.now().date()
        
        if hasattr(self, 'ids'):
            if 'prev_btn' in self.ids:
                self.ids.prev_btn.disabled = self.current_date <= self.min_date
            if 'next_btn' in self.ids:
                self.ids.next_btn.disabled = self.current_date >= self.max_date
        
        if self.current_date == today:
            self.selected_date = "TODAY"
        elif self.current_date == today + timedelta(days=1):
            self.selected_date = "TOMORROW"
        elif self.current_date == today + timedelta(days=2):
            self.selected_date = "DAY AFTER"
        else:
            self.selected_date = self.current_date.strftime('%d/%m/%Y')
    
    def previous_day(self):
        new_date = self.current_date - timedelta(days=1)
        if new_date >= self.min_date:
            self.current_date = new_date
            self.update_display()
            self.app.on_calendar_date_selected(self.current_date)
    
    def next_day(self):
        new_date = self.current_date + timedelta(days=1)
        if new_date <= self.max_date:
            self.current_date = new_date
            self.update_display()
            self.app.on_calendar_date_selected(self.current_date)


class StatsPopup(MDFloatLayout):
    home_team_name = StringProperty("")
    away_team_name = StringProperty("")
    first_team_name_display = StringProperty("")
    second_team_name_display = StringProperty("")
    first_team_goals_for = StringProperty("N/A")
    first_team_goals_against = StringProperty("N/A")
    second_team_goals_for = StringProperty("N/A")
    second_team_goals_against = StringProperty("N/A")
    first_team_label = StringProperty("") 
    second_team_label = StringProperty("")
    first_team_color = StringProperty("gray")
    second_team_color = StringProperty("gray")
    
    first_team_current_rank = StringProperty("-")
    first_team_last_rank = StringProperty("-")
    first_team_points = StringProperty("-")
    first_team_played = StringProperty("-")
    
    second_team_current_rank = StringProperty("-")
    second_team_last_rank = StringProperty("-")
    second_team_points = StringProperty("-")
    second_team_played = StringProperty("-")
    
    first_last_rank_color = StringProperty("#AAAAAA")
    second_last_rank_color = StringProperty("#AAAAAA")
    
    from_cache = BooleanProperty(False)
    cache_data = DictProperty({})
    
    def copy_team_rank_info(self, team_type, copy_type="current"):
        try:
            if team_type == 'first':
                current_rank = self.first_team_current_rank
                last_rank = self.first_team_last_rank
                opponent_current_rank = self.second_team_current_rank
                opponent_last_rank = self.second_team_last_rank
                team_name = self.first_team_name_display
            elif team_type == 'second':
                current_rank = self.second_team_current_rank
                last_rank = self.second_team_last_rank
                opponent_current_rank = self.first_team_current_rank
                opponent_last_rank = self.first_team_last_rank
                team_name = self.second_team_name_display
            else:
                MDApp.get_running_app().show_snackbar("❌ خطأ: نوع الفريق غير معروف")
                return

            def clean_rank(rank):
                cleaned = ''.join(filter(str.isdigit, str(rank))) 
                return cleaned if cleaned else '0'

            if copy_type == "current":
                team_rank = clean_rank(current_rank)
                opponent_rank = clean_rank(opponent_current_rank)
                copied_text = f"{team_rank}{opponent_rank}"
                message_type = "الترتيب الحالي"
            else:  
                team_rank = clean_rank(last_rank)
                opponent_rank = clean_rank(opponent_last_rank)
                copied_text = f"{team_rank}{opponent_rank}"
                message_type = "ترتيب الموسم الماضي"

            Clipboard.copy(copied_text)
            MDApp.get_running_app().show_snackbar(
                f"✅ تم نسخ {message_type} لـ {team_name}: {copied_text}", 
                duration=3
            )
            
            print(f"📋 تم النسخ: {copied_text} للفريق {team_name} ({message_type})")
            
        except Exception as e:
            print(f"❌ خطأ في النسخ: {e}")
            MDApp.get_running_app().show_snackbar(f"❌ فشل النسخ: {e}")


class LeagueItem(OneLineAvatarIconListItem):
    def __init__(self, league_name, league_id, **kwargs):
        super().__init__(**kwargs)
        self.text = league_name
        self.league_id = league_id
        self.selected = False

    def toggle_checkbox(self):
        self.selected = not self.selected
        self.ids.check.icon = "checkbox-marked" if self.selected else "checkbox-blank-outline"


class FavoriteLeagueItem(OneLineAvatarIconListItem):
    def __init__(self, league_name, league_id, **kwargs):
        super().__init__(**kwargs)
        self.text = league_name
        self.league_id = league_id

    def remove_favorite(self):
        app = MDApp.get_running_app()
        app.remove_favorite_league(self.league_id)


class LoadingWidget(MDBoxLayout):
    loading_text = StringProperty("Loading data...")
    progress_value = NumericProperty(0)
    status_text = StringProperty("Initializing...")


class ErrorWidget(MDBoxLayout):
    error_text = StringProperty("Loading error")


class OptimizedCompactMatchItem(MDCard):
    match_data = DictProperty({})
    is_fav = BooleanProperty(False)
    is_live = BooleanProperty(False)
    is_focused = BooleanProperty(False)
    
    league_name = StringProperty("")
    home_team = StringProperty("")
    away_team = StringProperty("")
    home_score = StringProperty("-")
    away_score = StringProperty("-")
    full_score = StringProperty("VS")
    match_status = StringProperty("")
    match_time = StringProperty("")
    events_text = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(match_data=self.on_match_data)
        self.bind(is_focused=self.on_focus_changed)

    def on_match_data(self, instance, value):
        if value:
            self.update_display()

    def on_focus_changed(self, instance, value):
        if value:
            self.md_bg_color = get_color_from_hex("#000000")
            self._update_text_colors(focused=True)
        else:
            if self.is_live:
                self.md_bg_color = get_color_from_hex("000000")
            else:
                self.md_bg_color = get_color_from_hex("#FFFFFF")
            self._update_text_colors(focused=False)

    def _update_text_colors(self, focused=False):
        Clock.schedule_once(lambda dt: self._apply_text_colors(focused), 0.1)

    def _apply_text_colors(self, focused):
        try:
            color_white = get_color_from_hex("#FFFFFF")
            color_black = get_color_from_hex("#000000")
            
            if focused:
                pass
        except:
            pass

    def update_display(self):
        try:
            self.league_name = self.match_data.get('league', 'Loading...')
            
            home_team_name = self.match_data.get('home_team', 'Home Team')
            away_team_name = self.match_data.get('away_team', 'Away Team')
            
            if len(home_team_name) > 15:
                self.home_team = home_team_name[:12] + "..."
            else:
                self.home_team = home_team_name

            if len(away_team_name) > 15:
                self.away_team = away_team_name[:12] + "..."
            else:
                self.away_team = away_team_name

            home_score = self.match_data.get('home_score')
            away_score = self.match_data.get('away_score')
            
            self.home_score = str(home_score) if home_score is not None else "-"
            self.away_score = str(away_score) if away_score is not None else "-"
            
            if home_score is not None and away_score is not None:
                self.full_score = f"{home_score}-{away_score}"
            else:
                self.full_score = "VS"
            
            status = self.match_data.get('status', 'NS')
            self.match_status = self.get_status_text(status)
            self.match_time = self.get_time_text(status)
            self.is_live = status in ['1H', '2H', 'HT', 'ET', 'P', 'BT', 'LIVE']
            
            if self.is_focused:
                self.md_bg_color = get_color_from_hex("#000000")
            elif self.is_live:
                self.md_bg_color = get_color_from_hex("000000") 
                self.elevation = 2 
            else:
                self.md_bg_color = get_color_from_hex("#FFFFFF")
                self.elevation = 1
            
        except Exception as e:
            print(f"Display update error: {e}")

    def get_status_text(self, status):
        status_map = {
            'NS': 'NS', '1H': '1H', 'HT': 'HT',
            '2H': '2H', 'ET': 'ET', 'P': 'P',
            'FT': 'FT', 'AET': 'AET', 'PEN': 'PEN',
            'BT': 'BT', 'SUSP': 'SUSP', 'INT': 'INT',
            'PST': 'PST', 'CANC': 'CANC', 'LIVE': 'LIVE'
        }
        return status_map.get(status, status)

    def get_time_text(self, status):
        if status in ['1H', '2H', 'LIVE']:
            elapsed = self.match_data.get('elapsed')
            return f"{elapsed}'" if elapsed else "Live"
        elif status == 'HT':
            return "HT"
        elif status == 'ET':
            return "ET"
        elif status == 'P':
            return "PEN"
        elif status == 'NS':
            time_str = self.match_data.get('time', '')
            if time_str:
                try:
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    return dt.strftime('%H:%M')
                except:
                    return time_str[:16]
        return self.match_status

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            hide_button = self.ids.hide_button
            
            safe_area_limit = self.x + self.width * 0.85
            
            if hide_button.collide_point(*touch.pos):
                return super().on_touch_down(touch)
            elif touch.x < safe_area_limit:
                touch.ud['in_match_item'] = True
                return True 
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            hide_button = self.ids.hide_button
            
            safe_area_limit = self.x + self.width * 0.85
            
            if not hide_button.collide_point(*touch.pos) and touch.x < safe_area_limit:
                app = MDApp.get_running_app()
                app.clear_match_focus()
                self.is_focused = True
                app.current_focused_match = self
                
                app.show_stats_popup_improved(self.match_data)
                return True
                
        return super().on_touch_up(touch)

    def hide_match(self):
        app = MDApp.get_running_app()
        match_id = self.match_data.get('id')
        
        is_in_hidden_list = app.is_hidden(match_id)
        
        if not is_in_hidden_list:
            app.add_hidden_match(self.match_data)
            app.show_snackbar(f"✅ Match hidden: {self.home_team} vs {self.away_team}")
            
            try:
                league_id = self.match_data.get('league_id')
                time_str = self.match_data.get('time', '')
                
                if league_id and time_str:
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    match_date = dt.strftime('%Y-%m-%d')
                    
                    success = app.storage.delete_match_from_scheduled_cache(
                        match_id=match_id,
                        league_id=league_id,
                        match_date=match_date
                    )
                    
                    if success:
                        print(f"✅ تم حذف المباراة من scheduled_matches_cache")
                    else:
                        print(f"⚠️ لم يتم العثور على المباراة في الكاش")
            except Exception as e:
                print(f"⚠️ خطأ في حذف المباراة من الكاش: {e}")
            
            app.remove_match_from_all_lists(match_id)
            
            parent = self.parent
            if parent:
                parent.remove_widget(self)
        else:
            app.remove_hidden_match(match_id)
            app.show_snackbar(f"✅ Match unhidden: {self.home_team} vs {self.away_team}")
            
            parent = self.parent
            if parent:
                parent.remove_widget(self)


# ==================== واجهة KV ====================

KV = '''
#:import get_color_from_hex kivy.utils.get_color_from_hex
#:import dp kivy.metrics.dp
#:import Animation kivy.animation.Animation

<CalendarHeader>:
    size_hint_y: None
    height: dp(50)
    orientation: 'horizontal'
    spacing: dp(10)
    padding: dp(5)
    
    MDIconButton:
        id: prev_btn
        icon: 'chevron-left'
        theme_text_color: 'Custom'
        text_color: get_color_from_hex("#2196F3")
        on_release: root.previous_day()
        
    MDRaisedButton:
        id: date_btn
        text: root.selected_date
        size_hint_x: 0.7
        md_bg_color: get_color_from_hex("#2196F3")
        
    MDIconButton:
        id: next_btn
        icon: 'chevron-right'
        theme_text_color: 'Custom'
        text_color: get_color_from_hex("#2196F3")
        on_release: root.next_day()

<StatsPopup>:
    size_hint: None, None
    size: dp(210), dp(170)
    pos_hint: {'center_x': 0.5, 'center_y': 0.9}
    md_bg_color: get_color_from_hex("#000000")
    radius: dp(45)
    opacity: 0
    
    MDBoxLayout:
        orientation: 'vertical'
        spacing: dp(5)
        padding: dp(15)
        pos_hint: {'center_x': 0.5, 'center_y': 0.5}
        
        MDLabel:
            text: "Live Stats"
            theme_text_color: 'Custom'
            text_color: get_color_from_hex("#2196F3")
            font_style: 'Caption'
            halign: 'center'
            bold: True
            size_hint_y: None
            height: dp(25)
        
        MDBoxLayout:
            orientation: 'horizontal'
            spacing: dp(15)
            size_hint_y: None
            height: dp(60)
            
            MDBoxLayout:
                orientation: 'vertical'
                size_hint_x: 0.35
                spacing: dp(0)
                
                MDBoxLayout:
                    orientation: 'horizontal'
                    spacing: dp(2)
                    size_hint_y: None
                    height: dp(5)
                    
                    MDLabel:
                        text: root.first_team_name_display
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#FFFFFF")
                        font_size: "12sp"
                        halign: 'center'
                        bold: True
                        text_size: self.width, None
                        size_hint_x: 0.5
                        
                MDBoxLayout:
                    orientation: 'vertical'
                    spacing: dp(10)
                    
                    MDIconButton:
                        icon: 'home'
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#2196F3")
                        icon_size: "15sp"
                        size_hint_x: 1
                        pos_hint: {"center_y": 0.5}
                        on_release: root.copy_team_rank_info('first', 'current')
                        

                MDBoxLayout:
                    orientation: 'horizontal'
                    spacing: dp(0)
                    
                    MDLabel:
                        text: root.first_team_goals_for
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#00FF00") if root.first_team_color == 'green' else (get_color_from_hex("#2196F3") if root.first_team_color == 'blue' else (get_color_from_hex("#FF0000") if root.first_team_color == 'red' else get_color_from_hex("#FFFFFF")))
                        font_size: "21sp"
                        halign: 'center'
                        bold: True
                        
                    MDLabel:
                        text: ":"
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#00FF00") if root.first_team_color == 'green' else (get_color_from_hex("#2196F3") if root.first_team_color == 'blue' else (get_color_from_hex("#FF0000") if root.first_team_color == 'red' else get_color_from_hex("#FFFFFF")))
                        font_size: "9sp"
                        halign: 'center'
                        size_hint_x: 0.1
                        
                    MDLabel:
                        text: root.first_team_goals_against
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#FF0000")
                        font_size: "21sp"
                        halign: 'center'
                        bold: True
            
            MDBoxLayout:
                orientation: 'vertical'
                size_hint_x: 0.35
                spacing: dp(0)
                
                MDBoxLayout:
                    orientation: 'horizontal'
                    spacing: dp(2)
                    size_hint_y: None
                    height: dp(5)
                    
                    MDLabel:
                        text: root.second_team_name_display
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#FFFFFF")
                        font_size: "12sp"
                        halign: 'center'
                        bold: True
                        text_size: self.width, None
                        size_hint_x: 0.5
                        
                MDBoxLayout:
                    orientation: 'vertical'
                    spacing: dp(10)
                    
                    MDIconButton:
                        icon: 'calendar-clock'
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#FF9800")
                        icon_size: "15sp"
                        size_hint_x: 1
                        pos_hint: {"center_y": 0.5}
                        on_release: root.copy_team_rank_info('first', 'last')
                
                MDBoxLayout:
                    orientation: 'horizontal'
                    spacing: dp(0)
                    
                    MDLabel:
                        text: root.second_team_goals_for
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#00FF00") if root.second_team_color == 'green' else (get_color_from_hex("#2196F3") if root.second_team_color == 'blue' else (get_color_from_hex("#FF0000") if root.second_team_color == 'red' else get_color_from_hex("#FFFFFF")))
                        font_size: "21sp"
                        halign: 'center'
                        bold: True
                        
                    MDLabel:
                        text: ":"
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#00FF00") if root.first_team_color == 'green' else (get_color_from_hex("#2196F3") if root.first_team_color == 'blue' else (get_color_from_hex("#FF0000") if root.first_team_color == 'red' else get_color_from_hex("#FFFFFF")))
                        font_size: "9sp"
                        halign: 'center'
                        size_hint_x: 0.1
                        
                    MDLabel:
                        text: root.second_team_goals_against
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#FF0000")
                        font_size: "21sp"
                        halign: 'center'
                        bold: True
        
        MDBoxLayout:
            orientation: 'horizontal'
            spacing: dp(15)
            size_hint_y: None
            height: dp(40)
            
            MDBoxLayout:
                orientation: 'vertical'
                size_hint_x: 0.35
                spacing: dp(2)
                
                MDLabel:
                    text: "Classement"
                    theme_text_color: 'Custom'
                    text_color: get_color_from_hex("#FFFFFF")
                    font_size: "8sp"
                    halign: 'center'
                
                MDBoxLayout:
                    orientation: 'horizontal'
                    spacing: dp(5)
                    
                    MDLabel:
                        text: root.first_team_current_rank
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#00FF00")
                        font_size: "15sp"
                        halign: 'center'
                        bold: True
                        
                    MDLabel:
                        text: "" + root.first_team_last_rank + ""
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#2196F3") if root.first_last_rank_color == "different_league_blue" else (get_color_from_hex("#00FF00") if root.first_last_rank_color == "normal" else (get_color_from_hex("#00FF00") if root.first_last_rank_color == "new_team" else get_color_from_hex("#FF0000")))
                        font_size: "15sp"
                        halign: 'center'
            
            MDLabel:
                text: "|"
                theme_text_color: 'Custom'
                text_color: get_color_from_hex("#666666")
                font_size: "12sp"
                halign: 'center'
                size_hint_x: 0.1
            
            MDBoxLayout:
                orientation: 'vertical'
                size_hint_x: 0.35
                spacing: dp(2)
                
                MDBoxLayout:
                    orientation: 'vertical'
                    spacing: dp(5)

                    MDLabel:
                        text: "Classement"
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#FFFFFF")
                        font_size: "8sp"
                        halign: 'center'
                    
                    MDBoxLayout:
                        orientation: 'horizontal'
                        spacing: dp(5)
                        
                        MDLabel:
                            text: root.second_team_current_rank
                            theme_text_color: 'Custom'
                            text_color: get_color_from_hex("#00FF00")
                            font_size: "15sp"
                            halign: 'center'
                            bold: True
                            
                        MDLabel:
                            text: "" + root.second_team_last_rank + ""
                            theme_text_color: 'Custom'
                            text_color: get_color_from_hex("#2196F3") if root.second_last_rank_color == "different_league_blue" else (get_color_from_hex("#00FF00") if root.second_last_rank_color == "normal" else (get_color_from_hex("#00FF00") if root.second_last_rank_color == "new_team" else get_color_from_hex("#FF0000")))
                            font_size: "15sp"
                            halign: 'center'

<LeagueItem>:
    IconLeftWidget:
        id: check
        icon: "checkbox-blank-outline"
        on_release: root.toggle_checkbox()

<FavoriteLeagueItem>:
    IconLeftWidget:
        icon: "star"
        theme_text_color: 'Custom'
        text_color: get_color_from_hex("#FFD700")

<LoadingWidget>:
    orientation: 'vertical'
    spacing: dp(20)
    padding: dp(20)
    size_hint_y: None
    height: dp(150)

    MDLabel:
        text: root.loading_text
        halign: 'center'
        theme_text_color: 'Secondary'
        font_style: 'H6'
        bold: True

    MDProgressBar:
        id: progress_bar
        value: root.progress_value
        type: "determinate"
        
    MDLabel:
        id: progress_text
        text: f"{int(root.progress_value)}%"
        halign: 'center'
        theme_text_color: 'Primary'
        font_style: 'H5'
        bold: True

    MDLabel:
        id: status_text
        text: root.status_text
        halign: 'center'
        theme_text_color: 'Secondary'
        font_style: 'Caption'

<ErrorWidget>:
    orientation: 'vertical'
    spacing: dp(20)
    padding: dp(20)
    size_hint_y: None
    height: dp(150)

    MDIcon:
        icon: "wifi-off"
        size_hint: None, None
        size: dp(48), dp(48)
        pos_hint: {'center_x': 0.5}
        theme_text_color: 'Secondary'

    MDLabel:
        text: root.error_text
        halign: 'center'
        theme_text_color: 'Secondary'

    MDRaisedButton:
        text: "Retry"
        pos_hint: {'center_x': 0.5}
        on_release: app.retry_loading()

<OptimizedCompactMatchItem>:
    size_hint_y: None
    height: dp(80)
    x: 0
    md_bg_color: get_color_from_hex("#000000") if root.is_focused else (get_color_from_hex("000000") if root.is_live else get_color_from_hex("#FFFFFF"))
    elevation: 3 if root.is_focused else (2 if root.is_live else 1)
    padding: dp(8)
    radius: dp(8)
    orientation: 'horizontal'
    spacing: dp(6)

    BoxLayout:
        orientation: 'vertical'
        size_hint_x: 0.20
        spacing: dp(2)
        
        MDLabel:
            id: time_label
            text: root.match_time
            font_style: 'Caption'
            theme_text_color: 'Custom'
            text_color: get_color_from_hex("#FFFFFF") if root.is_focused else (get_color_from_hex("#FF0000") if root.is_live else get_color_from_hex("#666666"))
            halign: 'center'
            bold: True
            font_size: '16sp'
            
        MDLabel:
            id: league_label
            text: root.league_name
            font_style: 'Caption'
            theme_text_color: 'Custom'
            text_color: get_color_from_hex("#CCCCCC") if root.is_focused else (get_color_from_hex("#FFFFFF") if root.is_live else get_color_from_hex("#999999"))
            halign: 'center'
            font_size: '9sp'
            shorten: True
            shorten_from: 'right'
            text_size: self.width, None

    BoxLayout:
        orientation: 'horizontal'
        size_hint_x: 0.65
        spacing: dp(5)

        BoxLayout:
            orientation: 'horizontal'
            size_hint_x: 0.48
            spacing: dp(3)
            
            MDLabel:
                id: home_team_label
                text: root.home_team
                font_style: 'Body2'
                halign: 'right'
                theme_text_color: 'Custom'
                text_color: get_color_from_hex("#FFFFFF") if root.is_focused or root.is_live else get_color_from_hex("#000000")
                shorten: True
                shorten_from: 'right'
                font_size: '12sp'
                text_size: self.width, None
                
            MDLabel:
                id: home_score_label
                text: root.home_score
                font_style: 'Subtitle1'
                halign: 'center'
                theme_text_color: 'Custom'
                text_color: get_color_from_hex("#FFFFFF") if root.is_focused or root.is_live else get_color_from_hex("#000000")
                bold: True
                font_size: '18sp'
                size_hint_x: 0.28

        BoxLayout:
            orientation: 'vertical'
            size_hint_x: 0.12
            spacing: dp(2)
            
            MDLabel:
                id: status_label
                text: root.match_status
                font_style: 'Caption'
                halign: 'center'
                theme_text_color: 'Custom'
                text_color: get_color_from_hex("#FF0000") if root.is_focused or root.is_live else get_color_from_hex("#666666")
                bold: root.is_focused or root.is_live
                font_size: '10sp'

        BoxLayout:
            orientation: 'horizontal'
            size_hint_x: 0.48
            spacing: dp(3)
            
            MDLabel:
                id: away_score_label
                text: root.away_score
                font_style: 'Subtitle1'
                halign: 'center'
                theme_text_color: 'Custom'
                text_color: get_color_from_hex("#FFFFFF") if root.is_focused or root.is_live else get_color_from_hex("#000000")
                bold: True
                font_size: '18sp'
                size_hint_x: 0.28
                
            MDLabel:
                id: away_team_label
                text: root.away_team
                font_style: 'Body2'
                halign: 'left'
                theme_text_color: 'Custom'
                text_color: get_color_from_hex("#FFFFFF") if root.is_focused or root.is_live else get_color_from_hex("#000000")
                shorten: True
                shorten_from: 'left'
                font_size: '12sp'
                text_size: self.width, None

    BoxLayout:
        orientation: 'vertical'
        size_hint_x: 0.15
        spacing: dp(2)
        
        MDIconButton:
            id: hide_button
            icon: 'eye-off'
            user_font_size: '20sp'
            theme_text_color: 'Custom'
            text_color: get_color_from_hex("#FF5252") if not root.is_focused else get_color_from_hex("#FF9999")
            on_release: root.hide_match()
            size_hint_y: 1

<BottomNavButton@MDFloatLayout>:
    size_hint: None, None
    size: dp(80), dp(70)
    icon: ''
    text: ''
    selected: False

    MDIconButton:
        icon: root.icon
        theme_text_color: 'Custom'
        text_color: get_color_from_hex("#2196F3") if root.selected else get_color_from_hex("#757575")
        pos_hint: {'center_x': 0.5, 'center_y': 0.6}
        user_font_size: '24sp'
        on_release: app.switch_tab(root.text.lower())

    MDLabel:
        text: root.text
        theme_text_color: 'Custom'
        text_color: get_color_from_hex("#2196F3") if root.selected else get_color_from_hex("#757575")
        font_style: 'Caption'
        halign: 'center'
        pos_hint: {'center_x': 0.5, 'center_y': 0.2}

BoxLayout:
    orientation: 'vertical'
    spacing: 0

    MDTopAppBar:
        id: topbar
        title: app.current_title
        elevation: 0
        md_bg_color: get_color_from_hex("#2196F3")
        specific_text_color: get_color_from_hex("#FFFFFF")
        left_action_items: 
            [
            ['arrow-left', lambda x: app.go_back()],
            ['menu', lambda x: app.open_menu()]
            ]
        right_action_items: 
            [
            ['autorenew', lambda x: app.actualaser_refresh()],
            ['update', lambda x: app.manual_refresh()]
            ]
        height: dp(52)

    RelativeLayout:
        id: stats_popup_container
        size_hint_y: None
        height: 0

    CalendarHeader:
        id: calendar_header

    BoxLayout:
        orientation: 'vertical'
        spacing: dp(6)
        padding: dp(6)

        BoxLayout:
            size_hint_y: None
            height: dp(35)
            spacing: dp(8)

            MDLabel:
                text: app.current_time
                font_style: 'H1'
                halign: 'center'
                theme_text_color: 'Primary'
                font_size: '1sp'
                size_hint_x: 1
                bold: True

        ScrollView:
            id: main_scroll
            MDGridLayout:
                id: main_list
                cols: 1
                adaptive_height: True
                spacing: dp(6)
                padding: dp(4)

    BoxLayout:
        id: bottom_nav
        size_hint_y: None
        height: dp(65)
        md_bg_color: get_color_from_hex("#FFFFFF")
        padding: dp(6)
        spacing: dp(4)

        BottomNavButton:
            id: btn_en_cours
            icon: 'play-circle'
            text: 'Live'
            selected: True

        BottomNavButton:
            id: btn_favoris
            icon: 'star'
            text: 'Favorites'

        BottomNavButton:
            id: btn_competitions
            icon: 'trophy'
            text: 'Leagues'

        BottomNavButton:
            id: btn_profil
            icon: 'account'
            text: 'Profile'
'''


# ==================== التطبيق الرئيسي ====================

class ProfessionalFootballApp(MDApp):
    current_tab = StringProperty('live')
    current_title = StringProperty('Live Matches')
    current_time = StringProperty('')
    
    matches = ListProperty()
    today_matches = ListProperty()
    favorites = ListProperty()
    hidden_matches = ListProperty()
    selected_leagues = ListProperty()
    favorite_leagues = ListProperty()
    country_leagues_map = DictProperty({})
    all_leagues = ListProperty([])
    
    auto_update = BooleanProperty(False)
    update_interval = NumericProperty(600)
    last_update = StringProperty('')
    request_count = NumericProperty(7500)
    max_requests = NumericProperty(7500)
    
    current_segment = StringProperty('today')
    
    api_key = StringProperty('ff5507928d7ea3382d5a8149db14e988')
    base_url = StringProperty('https://v3.football.api-sports.io')
    api_available = BooleanProperty(True)

    current_match_goals_for = NumericProperty(0)
    current_match_goals_against = NumericProperty(0)
    
    current_calendar_date = None
    calendar_mode = BooleanProperty(False)
    
    filter_ns_perfect_1_1_enabled = BooleanProperty(False)
    filter_ns_perfect_2_2_enabled = BooleanProperty(False)
    
    leagues_per_batch = NumericProperty(10)
    current_leagues_batch = NumericProperty(0)
    all_leagues_count = NumericProperty(0)
    show_load_more = BooleanProperty(False)
    grouped_leagues_cache = DictProperty({})
    
    current_focused_match = ObjectProperty(None, allownone=True)
    
    # ⭐⭐ تحديث: كاش الأهداف للمباريات المجدولة فقط
    scheduled_teams_goals_cache = DictProperty({})
    scheduled_teams_loading = DictProperty({})
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }
        self._is_loading = False
        self.leagues = []
        self.leagues_loaded = False
        self._update_event = None

        self.storage = SQLiteStorage()

        self.filtered_matches = []
        self.filter_results = {}
        self._is_filtering = False
        self.filter_condition = self.default_filter_condition
        self._auto_filter_event = None
        self.filter_interval = 600
        self.current_filter = "No Filter"

        self.current_calendar_date = datetime.now().date()
        self.calendar_mode = False
        
        self.team_stats_cache = {}
        self.team_standings_cache = {}
        self.cache_timeout = 300
        
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        self.futures = []
        
        self.scheduled_teams_goals_cache = {}
        self.scheduled_teams_loading = {}
        self._standings_api_locks = {}  # لإدارة طلبات API المكررة
    
    def build(self):
        self.theme_cls.primary_palette = 'Blue'
        self.theme_cls.theme_style = 'Light'
        
        self.selected_leagues = []

        self.update_time()
        Clock.schedule_interval(self.update_time, 60)
        
        self.load_favorites()
        self.load_hidden_matches()
        self.load_league_selection()
        self.load_favorite_leagues()
        self.load_filter_state()
        
        Clock.schedule_once(lambda dt: self.load_leagues_and_matches(), 0.5)
        Clock.schedule_once(lambda dt: self.schedule_auto_filter(), 10)
        
        return Builder.load_string(KV)
    
    def on_start(self):
        super().on_start()
    
    def on_stop(self):
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)
            
        if self._update_event:
            self._update_event.cancel()
            
        if self._auto_filter_event:
            self._auto_filter_event.cancel()
            
        self.save_favorites()
        self.save_hidden_matches()
        self.save_favorite_leagues()
        self.save_league_selection()        
        self.save_filter_state()        
        
        super().on_stop()

    def clear_match_focus(self):
        if self.current_focused_match:
            self.current_focused_match.is_focused = False
            self.current_focused_match = None

    # ⭐⭐ الدالة المحسنة لجلب أهداف فرق المباريات المجدولة فقط
    def fetch_scheduled_teams_goals(self, league_id, season, match_date):
        """جلب أهداف فرق المباريات المجدولة فقط (home last 3 home, away last 3 away)"""
        try:
            # 1. جلب المباريات المجدولة من الكاش
            scheduled_matches = self.storage.load_scheduled_matches_from_cache(match_date, league_id)
            
            if not scheduled_matches:
                print(f"⚠️ لا توجد مباريات مجدولة للدوري {league_id} بتاريخ {match_date}")
                return {}
            
            # 2. استخراج الفرق المشاركة مع تحديد الدور
            teams_to_fetch = []
            
            for match in scheduled_matches:
                home_team_id = match.get('home_team_id')
                away_team_id = match.get('away_team_id')
                
                if home_team_id:
                    # فريق المنزل: نحتاج last 3 home
                    teams_to_fetch.append({
                        'team_id': home_team_id,
                        'is_home_team': True,
                        'role': 'home'
                    })
                
                if away_team_id:
                    # فريق الضيف: نحتاج last 3 away
                    teams_to_fetch.append({
                        'team_id': away_team_id,
                        'is_home_team': False,
                        'role': 'away'
                    })
            
            print(f"📋 فرق المباريات المجدولة: {len(teams_to_fetch)} فريق ({len(scheduled_matches)} مباراة)")
            
            # 3. التحقق من الكاش أولاً
            all_teams_data = {}
            teams_to_fetch_from_api = []
            
            for team_info in teams_to_fetch:
                team_id = team_info['team_id']
                is_home_team = team_info['is_home_team']
                cache_key = f"{team_id}_{'home' if is_home_team else 'away'}"
                
                # التحقق من الكاش
                cached_data = self.get_team_goals_from_cache(team_id, league_id, season, is_home_team, match_date)
                
                if cached_data:
                    all_teams_data[cache_key] = cached_data
                else:
                    teams_to_fetch_from_api.append(team_info)
            
            # 4. جلب الفرق المتبقية من API
            if teams_to_fetch_from_api:
                print(f"🌐 جلب {len(teams_to_fetch_from_api)} فريق من API...")
                
                api_results = self._fetch_multiple_teams_last_3_matches(
                    teams_to_fetch_from_api, league_id, season
                )
                
                if api_results:
                    all_teams_data.update(api_results)
                    
                    # حفظ في الكاش
                    self._update_scheduled_teams_cache(league_id, season, match_date, api_results)
            
            print(f"✅ تم جلب إحصائيات {len(all_teams_data)} فريق")
            return all_teams_data
            
        except Exception as e:
            print(f"❌ خطأ في fetch_scheduled_teams_goals: {e}")
            return {}

    def _fetch_multiple_teams_last_3_matches(self, teams_list, league_id, season):
        """جلب last 3 matches لعدة فرق دفعة واحدة"""
        try:
            results = {}
            
            for team_info in teams_list:
                team_id = team_info['team_id']
                is_home_team = team_info['is_home_team']
                
                # جلب last 3 matches حسب الدور
                stats = self._fetch_team_last_3_matches(team_id, league_id, season, is_home_team)
                
                if stats:
                    stats_dict = self._parse_stats_to_dict(stats)
                    if stats_dict:
                        cache_key = f"{team_id}_{'home' if is_home_team else 'away'}"
                        results[cache_key] = stats_dict
            
            return results
            
        except Exception as e:
            print(f"❌ خطأ في _fetch_multiple_teams_last_3_matches: {e}")
            return {}

    def _fetch_team_last_3_matches(self, team_id, league_id, season, is_home_team):
        """جلب آخر 3 مباريات للفريق حسب الدور"""
        try:
            url = f"{self.base_url}/fixtures"
            params = {
                'team': team_id,
                'league': league_id,
                'season': season,
                'last': 15  
            }
            
            response = self.fetch_with_retry(url, params, max_retries=2)
            
            if response and response.status_code == 200:
                data = response.json()
                matches = data.get('response', [])
                
                if not matches:
                    return None
                
                finished_matches = []
                for match in matches:
                    fixture = match.get('fixture', {})
                    match_league = match.get('league', {})
                    
                    if (fixture.get('status', {}).get('short') == 'FT' and 
                        match_league.get('id') == league_id):
                        
                        teams = match.get('teams', {})
                        goals = match.get('goals', {})
                        
                        is_current_team_home = teams.get('home', {}).get('id') == team_id
                        
                        # نأخذ فقط المباريات بالدور المطلوب
                        if (is_home_team and is_current_team_home) or (not is_home_team and not is_current_team_home):
                            match_data = {
                                'home_goals': goals.get('home', 0),
                                'away_goals': goals.get('away', 0),
                                'is_home': is_current_team_home,
                                'date': fixture.get('date', '')
                            }
                            finished_matches.append(match_data)
                
                finished_matches.sort(key=lambda x: x['date'], reverse=True)
                
                last_3_matches = finished_matches[:3]
                
                if len(last_3_matches) == 0:
                    return None
                
                return self.calcul(last_3_matches, is_home=is_home_team)
                    
            return None
            
        except Exception as e:
            print(f"❌ خطأ في _fetch_team_last_3_matches: {e}")
            return None

    def get_team_goals_from_cache(self, team_id, league_id, season, is_home_team, match_date=None):
        """جلب بيانات الأهداف للفريق من الكاش"""
        try:
            if not match_date:
                match_date = datetime.now().strftime('%Y-%m-%d')
            
            cache_key = f"{league_id}_{season}_{match_date}"
            
            if cache_key in self.scheduled_teams_goals_cache:
                league_data = self.scheduled_teams_goals_cache[cache_key]
                team_key = f"{team_id}_{'home' if is_home_team else 'away'}"
                
                if team_key in league_data:
                    print(f"✅ استخدام الكاش المحمل للفريق {team_id} ({'home' if is_home_team else 'away'})")
                    return league_data[team_key]
            
            # محاولة تحميل من قاعدة البيانات
            cached_data = self.storage.load_scheduled_teams_goals_cache(league_id, season, match_date)
            
            if cached_data:
                self.scheduled_teams_goals_cache[cache_key] = cached_data
                
                team_key = f"{team_id}_{'home' if is_home_team else 'away'}"
                if team_key in cached_data:
                    print(f"✅ استخدام الكاش من قاعدة البيانات للفريق {team_id}")
                    return cached_data[team_key]
            
            return None
            
        except Exception as e:
            print(f"❌ Error in get_team_goals_from_cache: {e}")
            return None

    def _update_scheduled_teams_cache(self, league_id, season, match_date, new_data):
        """تحديث كاش الفرق المجدولة ببيانات جديدة"""
        try:
            cache_key = f"{league_id}_{season}_{match_date}"
            
            if cache_key in self.scheduled_teams_goals_cache:
                self.scheduled_teams_goals_cache[cache_key].update(new_data)
            else:
                self.scheduled_teams_goals_cache[cache_key] = new_data
            
            # حفظ في قاعدة البيانات
            success = self.storage.update_scheduled_teams_goals_cache(league_id, season, match_date, new_data)
            
            if success:
                print(f"✅ تم تحديث كاش الفرق المجدولة بـ {len(new_data)} فريق جديد")
            
            return success
            
        except Exception as e:
            print(f"❌ خطأ في تحديث الكاش: {e}")
            return False

    def _parse_stats_to_dict(self, stats_str):
        """تحويل نص الإحصائيات إلى قاموس"""
        try:
            if not stats_str or ":" not in stats_str:
                return None
            
            parts = stats_str.split(":")
            if len(parts) != 3:
                return None
            
            return {
                'color_type': parts[0],
                'goals_for': int(parts[1]),
                'goals_against': int(parts[2]),
                'matches_count': 3
            }
        except Exception as e:
            print(f"❌ Error parsing stats: {e}")
            return None

    def calcul(self, matches, is_home):
        """حساب الأهداف"""
        try:
            if not matches:
                return None
            
            total_goals_for = 0
            total_goals_against = 0
            zero_goal_matches = 0
            
            for match in matches:
                if is_home:
                    goals_for = match.get('home_goals', 0)
                    goals_against = match.get('away_goals', 0)
                else:
                    goals_for = match.get('away_goals', 0)
                    goals_against = match.get('home_goals', 0)
                
                total_goals_for += goals_for
                total_goals_against += goals_against
                
                if goals_for == 0:
                    zero_goal_matches += 1
            
            final_goals_for = min(total_goals_for, 9)
            final_goals_against = min(total_goals_against, 9)

            if final_goals_for >= 6:
                if zero_goal_matches == 0:
                    return "green:" + str(final_goals_for) + ":" + str(final_goals_against)
                elif zero_goal_matches == 1:
                    return "blue:" + str(final_goals_for) + ":" + str(final_goals_against)
                elif zero_goal_matches >= 2:
                    return "red:" + str(final_goals_for) + ":" + str(final_goals_against)
            else:
                return "green:" + str(final_goals_for) + ":" + str(final_goals_against)
                
        except Exception as e:
            print(f"Error in calcul: {e}")
            return None

    def fetch_matches_by_date_improved(self, target_date):
        """جلب المباريات: الكاش حسب الدوريات المختارة باستخدام set"""
        try:
            date_str = target_date.strftime('%Y-%m-%d')
            print(f"🔍 جاري البحث عن المباريات للتاريخ: {date_str}")

            required_league_ids = self.get_required_league_ids()
            all_cached_matches = []

            if required_league_ids:
                # استخدام set لجمع المباريات
                all_matches_set = set()
                
                for league_id in required_league_ids:
                    cached = self.storage.load_scheduled_matches_from_cache(date_str, league_id)
                    if cached:
                        # إضافة المباريات إلى set باستخدام معرف المباراة
                        for match in cached:
                            match_id = match.get('id')
                            if match_id:
                                all_matches_set.add((match_id, json.dumps(match, sort_keys=True)))
                
                # تحويل set إلى قائمة
                all_cached_matches = []
                for match_id, match_json in all_matches_set:
                    all_cached_matches.append(json.loads(match_json))
                    
                print(f"✅ تم تحميل {len(all_cached_matches)} مباراة من الكاش ({len(required_league_ids)} دوري)")
            else:
                print("⚠️ لا دوريات مختارة للكاش، سيتم تخطي الكاش")

            if self.filter_ns_perfect_1_1_enabled or self.filter_ns_perfect_2_2_enabled:
                print("🚫 الفلتر active - استخدام الكاش فقط مع حذف المباريات المخفية والمفضلة أولًا")

                # فلترة المباريات المخفية والمفضلة قبل أي فلترة أخرى
                non_hidden_and_favorites_removed = self.filter_out_hidden_and_favorite_matches(all_cached_matches)

                print(f"📊 النتيجة من الكاش بعد حذف المخفية والمفضلة: {len(non_hidden_and_favorites_removed)} مباراة")
                return non_hidden_and_favorites_removed

            print("🌐 تحميل جميع المباريات مرة واحدة من API...")
            url = f"{self.base_url}/fixtures"
            params = {'date': date_str}

            response = self.fetch_with_retry(url, params, max_retries=2)
            matches_from_api = []
            
            if response and response.status_code == 200:
                data = response.json()
                if data.get('response'):
                    api_matches = self.process_api_response_improved(data['response'])
                    matches_from_api = api_matches

                    # تجميع المباريات حسب الدوري وحفظها في الكاش
                    matches_by_league = {}
                    for match in api_matches:
                        league_id = match.get('league_id')
                        if league_id:
                            if league_id not in matches_by_league:
                                matches_by_league[league_id] = []
                            matches_by_league[league_id].append(match)

                    for league_id, league_matches in matches_by_league.items():
                        self.storage.save_scheduled_matches_to_cache(date_str, league_id, league_matches)

            # دمج المباريات مع إزالة التكرارات باستخدام set
            all_matches = all_cached_matches + matches_from_api
            
            seen_ids = set()
            unique_matches = []
            
            for match in all_matches:
                match_id = match.get('id')
                if match_id and match_id not in seen_ids:
                    seen_ids.add(match_id)
                    unique_matches.append(match)

            # فلترة المباريات المخفية باستخدام set
            hidden_ids = {m.get('id') for m in self.hidden_matches}
            unique_matches = [
                match for match in unique_matches 
                if match.get('id') not in hidden_ids
            ]

            print(f"📊 النتيجة النهائية: {len(unique_matches)} مباراة ({len(all_cached_matches)} من الكاش، {len(matches_from_api)} من API)")

            return unique_matches

        except Exception as e:
            print(f"❌ خطأ في جلب المباريات: {e}")
            if 'all_cached_matches' in locals() and all_cached_matches:
                print(f"🔄 الرجوع للكاش بسبب خطأ: {len(all_cached_matches)} مباراة")
                return all_cached_matches
            return []

    def filter_out_hidden_matches_immediately(self, matches_list):
        """فلترة المباريات المخفية باستخدام set لتحسين الأداء"""
        if not matches_list:
            return []
        
        # استخدام set للكشف السريع عن المباريات المخفية
        hidden_ids = {m.get('id') for m in self.hidden_matches}
        
        filtered = []
        hidden_count = 0
        
        for match in matches_list:
            match_id = match.get('id')
            
            if match_id in hidden_ids:
                hidden_count += 1
                continue
            
            filtered.append(match)
        
        if hidden_count > 0:
            print(f"🚫 فلترة فورية: تم إزالة {hidden_count} مباراة مخفية")
        
        return filtered

    def filter_out_hidden_and_favorite_matches(self, matches_list):
        """فلترة المباريات المخفية والمفضلة باستخدام set"""
        if not matches_list:
            return []
        
        hidden_ids = {m.get('id') for m in self.hidden_matches}
        favorite_ids = {f.get('id') for f in self.favorites}
        
        filtered = []
        hidden_count = 0
        favorite_count = 0
        
        for match in matches_list:
            match_id = match.get('id')

            if match_id in hidden_ids:
                hidden_count += 1
                continue

            if match_id in favorite_ids:
                favorite_count += 1
                continue
            
            filtered.append(match)
        
        if hidden_count > 0 or favorite_count > 0:
            print(f"🚫 فلترة شاملة: تم إزالة {hidden_count} مخفية و {favorite_count} مفضلة")
        
        return filtered

    def load_filter_state(self):
        self.filter_ns_perfect_1_1_enabled = self.storage.load_filter_state('filter_ns_perfect_1_1_enabled')
        self.filter_ns_perfect_2_2_enabled = self.storage.load_filter_state('filter_ns_perfect_2_2_enabled')
            
    def save_filter_state(self):
        self.storage.save_filter_state('filter_ns_perfect_1_1_enabled', self.filter_ns_perfect_1_1_enabled)
        self.storage.save_filter_state('filter_ns_perfect_2_2_enabled', self.filter_ns_perfect_2_2_enabled)

    def filter_ns_perfect_1_1_batch(self, matches_batch):
        """فلتر perfect 1_1 مع التحقق من ترتيب الموسم الماضي وحفظ في favorites"""
        try:
            filtered_matches = []
            
            for match_data in matches_batch:
                try:
                    match_id = match_data.get('id')
                    home_team_id = match_data.get('home_team_id')
                    away_team_id = match_data.get('away_team_id')
                    league_id = match_data.get('league_id')
                    season = match_data.get('season')
                    
                    if not season:
                        season = datetime.now().year
                    
                    try:
                        season = int(season)
                        last_season = season - 1
                    except:
                        filtered_matches.append(match_data)
                        self._auto_save_to_favorites_if_not_exists(
                            match_data,
                            "N/A  //  _rank",
                            "Invalid season format"
                        )
                        continue

                    # ===== جلب ترتيب الموسم الماضي =====
                    home_last_data = self._fetch_last_season_standings_with_cache(home_team_id, league_id, last_season)
                    away_last_data = self._fetch_last_season_standings_with_cache(away_team_id, league_id, last_season)
                    
                    home_last_rank = home_last_data.get('current_rank', 'N/A') if home_last_data else 'N/A'
                    away_last_rank = away_last_data.get('current_rank', 'N/A') if away_last_data else 'N/A'
                    
                    # إذا كان أي فريق جديد أو غير موجود في الموسم الماضي، نعتبره مقبولًا
                    if home_last_rank in ("N/A", "NEW") or away_last_rank in ("N/A", "NEW"):
                        filtered_matches.append(match_data)
                        self._auto_save_to_favorites_if_not_exists(
                            match_data,
                            "N/A // yt7sb auto (80)",
                            "New or missing in last season"
                        )
                        continue

                    # ===== الشروط الأساسية للفلتر =====
                    status = match_data.get('status', 'NS')
                    if status not in ['NS', 'TBD']:
                        continue
                    
                    time_str = match_data.get('time', '')
                    match_date = ""
                    if time_str:
                        try:
                            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                            match_date = dt.strftime('%Y-%m-%d')
                        except:
                            match_date = datetime.now().strftime('%Y-%m-%d')
                    
                    home_result = self._get_team_goals_for_filter_with_cache(
                        home_team_id, league_id, season, True, match_date
                    )
                    away_result = self._get_team_goals_for_filter_with_cache(
                        away_team_id, league_id, season, False, match_date
                    )
                    
                    if home_result[0] is None or away_result[0] is None:
                        filtered_matches.append(match_data)
                        self._auto_save_to_favorites_if_not_exists(
                            match_data,
                            "suprimée   or cheeck 2",
                            "Incomplete match data"
                        )
                        continue
                        
                    home_goals, home_count = home_result
                    away_goals, away_count = away_result
                    
                    if home_count < 3 or away_count < 3:
                        filtered_matches.append(match_data)
                        self._auto_save_to_favorites_if_not_exists(
                            match_data,
                            "suprimée   or cheeck 2",
                            "Not enough matches"
                        )
                        continue
                    
                    try:
                        home_goals_int = int(home_goals)
                        away_goals_int = int(away_goals)
                    except (ValueError, TypeError):
                        continue
                    
                except Exception as e:
                    print(f"perfect 1_1 error for match {match_data.get('id')}: {e}")
                    continue
            
            return filtered_matches
            
        except Exception as e:
            print(f"❌ خطأ في filter_ns_perfect_1_1_batch: {e}")
            return []

    def filter_ns_perfect_2_2_batch(self, matches_batch):
        """فلتر perfect 2_2 مع الفحوصات المشددة"""
        try:
            filtered_matches = []
            forbidden_groups = [
                {
                    'current_rank': {(1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (2, 10), (2, 11), (2, 12), (3, 10), (3, 11), (3, 12), (4, 10), (4, 11), (4, 12), (4, 13)},
                    'last_season': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (2, 10), (3, 10), (4, 10), (4, 11), (4, 12)},
                    'goals_condition': {(1, 1), (1, 2), (1, 3)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (4, 0), (4, 1), (4, 2), (4, 3), (5, 0), (5, 1), (5, 2), (5, 3), (6, 0), (6, 1), (6, 2), (6, 3), (7, 2), (7, 3)}
                },
                {
                    'current_rank': {(1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'last_season': {(1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'goals_condition': {(2, 2), (2, 3), (2, 4), (2, 5), (2, 6)},  
                    'goals_latest': {(3, 0), (3, 1), (4, 0), (4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 7), (1, 8), (1, 9), (2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'last_season': {(1, 7), (1, 8), (1, 9), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'goals_condition': {(2, 7), (2, 8), (2, 9)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (4, 5), (4, 6), (4, 7), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (5, 7), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (6, 7), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'last_season': {(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (3, 10), (3, 11), (3, 12), (4, 10), (4, 11), (4, 12)},
                    'goals_condition': {(3, 1), (3, 2), (3, 3)},
                    'goals_latest': {(4, 0), (4, 1), (4, 2), (5, 0), (5, 1), (5, 2), (5, 3), (6, 0), (6, 1), (6, 2), (6, 3), (7, 0), (7, 1), (7, 2), (7, 3), (8, 1), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'last_season': {(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (3, 10), (3, 11), (3, 12), (4, 10), (4, 11), (4, 12)},
                    'goals_condition': {(3, 4)},
                    'goals_latest': {(4, 0), (4, 1), (4, 2), (4, 3), (5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (6, 5), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (2, 10), (2, 11), (3, 10), (3, 11), (4, 10), (4, 11)},
                    'last_season': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (2, 10), (2, 11), (3, 10), (3, 11), (4, 10), (4, 11)},
                    'goals_condition': {(3, 5)},
                    'goals_latest': {(4, 0), (4, 1), (4, 2), (5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (2, 10), (2, 11), (3, 10), (3, 11), (4, 10), (4, 11)},
                    'last_season': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (2, 10), (2, 11), (3, 10), (3, 11), (4, 10), (4, 11)},
                    'goals_condition': {(3, 6)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (4, 5), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(2, 6), (2, 7), (2, 8), (2, 9), (3, 6), (3, 7), (3, 8), (3, 9), (4, 6), (4, 7), (4, 8), (4, 9), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'last_season': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'goals_condition': {(3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(4, 3), (4, 4), (4, 5), (5, 3), (5, 4), (5, 5), (5, 6), (6, 3), (6, 4), (6, 5), (6, 6), (7, 3), (7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (4, 5), (4, 6), (4, 7), (4, 8)},
                    'last_season': {(1, 5), (1, 6), (1, 7), (1, 8), (2, 5), (2, 6), (2, 7), (2, 8), (3, 5), (3, 6), (3, 7), (3, 8), (4, 5), (4, 6), (4, 7), (4, 8)},
                    'goals_condition': {(4, 0), (4, 1), (4, 2)},
                    'goals_latest': {(6, 0), (6, 1), (6, 2), (6, 3), (7, 1), (7, 2), (7, 3), (8, 1), (8, 2), (8, 3), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (4, 5), (4, 6), (4, 7), (4, 8)},
                    'last_season': {(1, 5), (1, 6), (1, 7), (1, 8), (2, 5), (2, 6), (2, 7), (2, 8), (3, 5), (3, 6), (3, 7), (3, 8), (4, 5), (4, 6), (4, 7), (4, 8)},
                    'goals_condition': {(4, 3), (4, 4)},
                    'goals_latest': {(5, 1), (5, 2), (6, 1), (6, 2), (6, 3), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (4, 5), (4, 6), (4, 7), (4, 8)},
                    'last_season': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9)},
                    'goals_condition': {(4, 5), (4, 6), (4, 7), (4, 8), (4, 9)},
                    'goals_latest': {(7, 3), (7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (3, 10), (3, 11), (3, 12), (4, 10), (4, 11), (4, 12)},
                    'last_season': {(1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'goals_condition': {(5, 1)},
                    'goals_latest': {(9, 1), (9, 2)}
                },
                {
                    'current_rank': {(1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (3, 10), (3, 11), (3, 12), (4, 10), (4, 11), (4, 12)},
                    'last_season': {(1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'goals_condition': {(5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4)},
                    'goals_latest': {(6, 0), (6, 1), (6, 2), (7, 0), (7, 1), (7, 2), (7, 3), (8, 1), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'last_season': {(1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (3, 10), (4, 10)},
                    'goals_condition': {(6, 5), (6, 6)},
                    'goals_latest': {(7, 2), (7, 3), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'last_season': {(1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (3, 10), (4, 10)},
                    'goals_condition': {(4, 5), (4, 6), (4, 7), (5, 5), (5, 6), (5, 7), (5, 8), (5, 9)},
                    'goals_latest': {(8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14)},
                    'goals_condition': {(2, 2), (2, 3), (2, 4)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (4, 0), (4, 1), (4, 2), (4, 3), (5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (6, 0), (6, 1), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 8), (1, 9), (2, 8), (2, 9), (3, 8), (3, 9), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14)},
                    'goals_condition': {(2, 5)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (3, 3), (4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (4, 5), (4, 6), (5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (6, 1), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(1, 8), (1, 9), (2, 8), (2, 9), (3, 8), (3, 9), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 12), (10, 13), (10, 14)},
                    'goals_condition': {(2, 6)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (3, 3), (4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (4, 5), (4, 6), (5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (6, 1), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (10, 12), (10, 13), (10, 14)},
                    'goals_condition': {(2, 7), (2, 8), (2, 9)},
                    'goals_latest': {(3, 1), (3, 2), (3, 3), (4, 1), (4, 2), (4, 3), (4, 4), (4, 5), (5, 1), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (6, 1), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (6, 7), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(1, 7), (1, 8), (1, 9), (2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14)},
                    'goals_condition': {(3, 1), (3, 2), (3, 3)},
                    'goals_latest': {(5, 0), (5, 1), (5, 2), (5, 3), (6, 0), (6, 1), (6, 2), (6, 3), (7, 0), (7, 1), (7, 2), (7, 3), (8, 1), (8, 2), (8, 3), (9, 1), (9, 2), (9, 3)}
                },
                {
                    'current_rank': {(1, 7), (1, 8), (1, 9), (2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14)},
                    'goals_condition': {(3, 4)},
                    'goals_latest': {(5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9), (4, 7), (4, 8), (4, 9), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (10, 12), (10, 13), (10, 14)},
                    'goals_condition': {(3, 5), (3, 6)},
                    'goals_latest': {(5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(6, 9), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (10, 12), (10, 13), (10, 14)},
                    'goals_condition': {(3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (3, 10), (4, 10)},
                    'last_season': {(5, 8), (5, 9), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14)},
                    'goals_condition': {(4, 2), (4, 3)},
                    'goals_latest': {(8, 1), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (3, 10), (4, 10)},
                    'last_season': {(5, 8), (5, 9), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14)},
                    'goals_condition': {(4, 4)},
                    'goals_latest': {(5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (3, 10), (3, 11), (3, 12), (3, 13), (4, 10)},
                    'last_season': {(5, 8), (5, 9), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14)},
                    'goals_condition': {(4, 5), (4, 6), (4, 7), (4, 8)},
                    'goals_latest': {(5, 1), (5, 2), (5, 3), (5, 4), (6, 0), (6, 1), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (2, 14), (3, 10), (4, 10)},
                    'last_season': {(5, 8), (5, 9), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14)},
                    'goals_condition': {(5, 4)},
                    'goals_latest': {(7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (2, 10), (2, 14), (3, 10), (4, 10)},
                    'last_season': {(5, 8), (5, 9), (6, 8), (6, 9), (7, 8), (7, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14)},
                    'goals_condition': {(5, 5), (5, 6)},
                    'goals_latest': {(7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(5, 8), (5, 9), (6, 8), (6, 9), (5, 10), (5, 11), (6, 10), (6, 11)},
                    'last_season': {(1, 8), (1, 9), (2, 8), (2, 9), (3, 8), (3, 9), (4, 8), (4, 9), (1, 10), (2, 10), (3, 10), (4, 10)},
                    'goals_condition': {(1, 1), (1, 2), (1, 3), (1, 4)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (3, 3), (4, 0), (4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 3), (5, 4)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14)},
                    'last_season': {(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (3, 10), (4, 10)},
                    'goals_condition': {(2, 4)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (3, 3), (4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (5, 10), (5, 11), (5, 12), (6, 10), (6, 11), (6, 12)},
                    'last_season': {(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (3, 10), (4, 10)},
                    'goals_condition': {(2, 2), (2, 3)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (3, 3), (4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16)},
                    'last_season': {(1, 7), (1, 8), (1, 9), (2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (3, 10), (3, 11), (3, 12), (3, 13), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'goals_condition': {(2, 5), (2, 6), (2, 7), (2, 8), (2, 9)},
                    'goals_latest': {(5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (6, 7),(7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (5, 10), (5, 11), (5, 12), (6, 10), (6, 11), (6, 12)},
                    'last_season': {(1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (2, 11), (3, 10), (3, 11), (4, 10), (4, 11)},
                    'goals_condition': {(3, 3), (3, 4), (4, 3), (4, 4)},
                    'goals_latest': {(6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (5, 10), (5, 11), (5, 12), (6, 10), (6, 11), (6, 12)},
                    'last_season': {(1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (2, 13), (3, 10), (3, 11), (3, 12), (3, 13), (4, 10), (4, 11), (4, 12), (4, 13)},
                    'goals_condition': {(3, 5), (3, 6)},
                    'goals_latest': {(7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14)},
                    'last_season': {(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (3, 10), (3, 11), (3, 12), (4, 10), (4, 11), (4, 12)},
                    'goals_condition': {(3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(4, 2), (4, 3), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14)},
                    'last_season': {(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (3, 10), (4, 10)},
                    'goals_condition': {(4, 5), (4, 6), (4, 7)},
                    'goals_latest': {(6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9)},
                    'last_season': {(1, 3), (1, 4), (1, 5), (1, 6), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (4, 5), (4, 6), (4, 7), (4, 8)},
                    'goals_condition': {(5, 5), (5, 6), (5, 7)},
                    'goals_latest': {(7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15)},
                    'last_season': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16)},
                    'goals_condition': {(1, 3), (1, 4), (1, 5)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (4, 0), (4, 1), (4, 2), (4, 3), (5, 0), (5, 1), (5, 2), (5, 3), (5, 4)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9)},
                    'last_season': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15)},
                    'goals_condition': {(2, 1), (2, 2), (2, 3)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (3, 3), (3, 4), (4, 2), (4, 3), (4, 4), (5, 1), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15)},
                    'last_season': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15)},
                    'goals_condition': {(2, 4)},
                    'goals_latest': {(5, 1), (5, 2), (5, 3), (6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (5, 17), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16)},
                    'last_season': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15)},
                    'goals_condition': {(2, 5), (2, 6)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (3, 3), (4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15)},
                    'last_season': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (13, 14), (13, 15), (14, 15), (14, 16)},
                    'goals_condition': {(2, 7), (2, 8), (2, 9)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (5, 10), (6, 10)},
                    'last_season': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (6, 10), (7, 10), (8, 10), (9, 10)},
                    'goals_condition': {(3, 2), (3, 3), (3, 4)},
                    'goals_latest': {(8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15)},
                    'last_season': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (13, 14), (13, 15), (14, 15), (14, 16)},
                    'goals_condition': {(3, 5), (3, 6)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15)},
                    'last_season': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (13, 14), (13, 15), (14, 15), (14, 16)},
                    'goals_condition': {(3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15)},
                    'last_season': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15)},
                    'goals_condition': {(4, 5), (4, 6), (4, 7)},
                    'goals_latest': {(5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(7, 8), (7, 9), (8, 9), (7, 10), (7, 11), (7, 12), (8, 10), (8, 11), (8, 12)},
                    'last_season': {(1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (2, 11), (3, 10), (3, 11), (3, 12), (4, 10), (4, 11), (4, 12)},
                    'goals_condition': {(2, 2), (2, 3), (2, 4)},  
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (3, 3), (4, 0), (4, 1), (4, 2), (4, 3), (5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(7, 8), (7, 9), (8, 9), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14)},
                    'last_season': {(1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (2, 11), (3, 10), (3, 11), (3, 12), (4, 10), (4, 11), (4, 12)},
                    'goals_condition': {(2, 5), (2, 6), (2, 7), (2, 8), (2, 9)},
                    'goals_latest': {(5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(7, 8), (7, 9), (8, 9), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14)},
                    'last_season': {(1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (2, 11), (3, 10), (3, 11), (4, 10), (4, 11), (4, 12)},
                    'goals_condition': {(3, 3), (3, 4), (4, 5), (4, 6)},
                    'goals_latest': {(6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(7, 8), (7, 9), (8, 9), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14)},
                    'last_season': {(1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (2, 11), (3, 10), (3, 11), (4, 10), (4, 11), (4, 12)},
                    'goals_condition': {(3, 5), (3, 6), (3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15)},
                    'last_season': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (5, 17), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16), (6, 17)},
                    'goals_condition': {(0, 1), (0, 2), (0, 3), (0, 4)},
                    'goals_latest': {(2, 0), (2, 1), (2, 2), (3, 0), (3, 1), (3, 2), (3, 3), (4, 1), (4, 2), (4, 3), (4, 4)}
                },
                {
                    'current_rank': {(7, 8), (7, 9), (8, 9), (7, 10), (7, 11), (7, 12), (8, 10), (8, 11), (8, 12)},
                    'last_season': {(5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 12), (10, 13), (10, 14), (10, 15)},
                    'goals_condition': {(2, 2), (2, 3)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (4, 0), (4, 1), (4, 2), (4, 3), (5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(7, 8), (7, 9), (8, 9), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15)},
                    'last_season': {(5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 12), (10, 13), (10, 14), (10, 15)},
                    'goals_condition': {(2, 4)},
                    'goals_latest': {(4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (5, 1), (5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15)},
                    'last_season': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (13, 14), (13, 15), (14, 15), (14, 16)},
                    'goals_condition': {(2, 5), (2, 6)},
                    'goals_latest': {(3, 3), (3, 4), (4, 3), (4, 4), (4, 5), (4, 6), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(7, 10), (7, 11), (7, 12), (8, 10), (8, 11), (8, 12)},
                    'last_season': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (13, 14), (13, 15), (14, 15), (14, 16)},
                    'goals_condition': {(2, 7), (2, 8), (2, 9)},
                    'goals_latest': {(3, 1), (3, 2), (3, 3), (4, 2), (4, 3), (4, 4), (4, 5), (5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(7, 10), (7, 11), (7, 12), (8, 10), (8, 11), (8, 12)},
                    'last_season': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (13, 14), (13, 15), (14, 15), (14, 16)},
                    'goals_condition': {(3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (4, 5), (5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15)},
                    'last_season': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (13, 14), (13, 15), (14, 15), (14, 16)},
                    'goals_condition': {(3, 5), (3, 6)},
                    'goals_latest': {(5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(7, 12), (7, 13), (7, 14), (7, 15), (8, 12), (8, 13), (8, 14), (8, 15)},
                    'last_season': {(5, 9), (6, 9), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15)},
                    'goals_condition': {(4, 5), (4, 6), (4, 7), (4, 8), (4, 9)},
                    'goals_latest': {(5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15)},
                    'last_season': {(5, 9), (6, 9), (7, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (13, 14), (13, 15), (14, 15), (14, 16)},
                    'goals_condition': {(5, 5), (5, 6), (5, 7), (5, 8), (5, 9)},
                    'goals_latest': {(6, 4), (6, 5), (6, 6), (6, 7), (7, 3), (7, 4), (7, 5), (7, 6), (7, 7), (8, 3), (8, 4), (8, 5), (8, 6), (8, 7), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 13), (11, 14), (11, 15), (12, 13), (12, 14), (12, 15)},
                    'last_season': {(2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9), (4, 7), (4, 8), (4, 9), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'goals_condition': {(2, 2), (2, 3), (2, 4)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (3, 3), (4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 13), (12, 14), (12, 15), (12, 16)},
                    'last_season': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (2, 10), (3, 10), (4, 10)},
                    'goals_condition': {(3, 3), (3, 4), (3, 5), (3, 6), (3, 7)},
                    'goals_latest': {(6, 1), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(9, 15), (10, 15), (10, 16), (10, 17), (10, 18), (11, 15), (11, 16), (11, 17), (11, 18), (12, 15), (12, 16), (12, 17), (12, 18), (13, 15), (13, 16), (13, 17), (13, 18), (14, 15), (14, 16), (14, 17), (14, 18)},
                    'last_season': {(1, 7), (1, 8), (1, 9), (2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'goals_condition': {(4, 5), (4, 6), (4, 7)},
                    'goals_latest': {(6, 3), (6, 4), (6, 5), (6, 6), (7, 3), (7, 4), (7, 5), (8, 3), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(9, 12), (9, 13), (9, 14), (10, 12), (10, 13), (10, 14), (11, 13), (11, 14), (12, 13), (12, 14), (13, 14)},
                    'last_season': {(1, 7), (1, 8), (1, 9), (2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'goals_condition': {(4, 5), (4, 6), (4, 7)},
                    'goals_latest': {(6, 3), (6, 4), (6, 5), (6, 6), (7, 3), (7, 4), (7, 5), (8, 3), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(10, 13), (10, 14), (10, 15), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 13), (12, 14), (12, 15), (12, 16), (12, 17), (13, 14), (13, 15), (13, 16), (13, 17), (14, 15), (14, 16), (14, 17), (14, 18)},
                    'last_season': {(5, 8), (5, 9), (6, 8), (6, 9), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 16), (5, 17), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (9, 17), (10, 11), (10, 12), (10, 13), (10, 14)},
                    'goals_condition': {(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)},
                    'goals_latest': {(2, 0), (2, 1), (2, 2), (3, 0), (3, 1), (3, 2)}
                },
                {
                    'current_rank': {(10, 13), (10, 14), (10, 15), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 13), (12, 14), (12, 15), (12, 16), (12, 17), (13, 14), (13, 15), (13, 16), (13, 17), (14, 15), (14, 16), (14, 17), (14, 18)},
                    'last_season': {(5, 8), (5, 9), (6, 8), (6, 9), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 16), (5, 17), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (9, 17), (10, 11), (10, 12), (10, 13), (10, 14)},
                    'goals_condition': {(1, 1), (1, 2), (1, 3), (1, 4), (1, 5)},
                    'goals_latest': {(2, 2), (2, 3), (2, 4), (2, 5), (3, 1), (3, 2), (3, 3), (3, 4), (3, 5)}
                },
                {
                    'current_rank': {(9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 12), (10, 13), (10, 14), (10, 15)},
                    'last_season': {(5, 9), (6, 9), (7, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 12), (8, 13), (8, 14), (8, 15), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (9, 17), (10, 11), (10, 12), (10, 13), (10, 14), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (12, 16), (13, 14), (13, 15), (13, 16)},
                    'goals_condition': {(2, 3), (2, 4), (2, 5)},
                    'goals_latest': {(6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 13), (12, 14), (12, 15), (12, 16), (12, 17), (13, 14), (13, 15), (13, 16), (13, 17), (14, 15), (14, 16), (14, 17), (14, 18)},
                    'last_season': {(6, 9), (7, 9), (8, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (9, 17), (10, 11), (10, 12), (10, 13), (10, 14), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (12, 16)},
                    'goals_condition': {(2, 6), (2, 7)},
                    'goals_latest': {(4, 5), (4, 6), (5, 5), (5, 6), (5, 7), (6, 5), (6, 6)},
                    'current_rank': {(9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 13), (12, 14), (12, 15), (12, 16), (12, 17), (13, 14), (13, 15), (13, 16), (13, 17), (14, 15), (14, 16), (14, 17), (14, 18)},
                    'last_season': {(6, 9), (7, 9), (8, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (9, 17), (10, 11), (10, 12), (10, 13), (10, 14), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (12, 16)},
                    'goals_condition': {(2, 9)},
                    'goals_latest': {(3, 3), (3, 4), (3, 5), (3, 6), (4, 3), (4, 4), (4, 5), (4, 6), (4, 7), (5, 4), (5, 5), (5, 6), (5, 7)}
                },
                {
                    'current_rank': {(10, 13), (10, 14), (10, 15), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 13), (12, 14), (12, 15), (12, 16), (12, 17), (13, 14), (13, 15), (13, 16), (13, 17), (14, 15), (14, 16), (14, 17), (14, 18)},
                    'last_season': {(9, 13), (9, 14), (9, 15), (9, 16), (9, 17), (10, 11), (10, 12), (10, 13), (10, 14), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (12, 16), (13, 14), (13, 15), (13, 16), (13, 17)},
                    'goals_condition': {(3, 3), (3, 4)},
                    'goals_latest': {(4, 1), (4, 2), (4, 3), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(9, 13), (9, 14), (9, 15), (10, 13), (10, 14), (10, 15), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 13), (12, 14), (12, 15), (12, 16), (12, 17), (13, 14), (13, 15), (13, 16), (13, 17), (14, 15), (14, 16), (14, 17), (14, 18)},
                    'last_season': {(10, 14), (10, 15), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (12, 16), (13, 14), (13, 15), (13, 16), (13, 17), (14, 15), (14, 16)},
                    'goals_condition': {(3, 5), (3, 6)},
                    'goals_latest': {(5, 2), (5, 3), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(9, 12), (9, 13), (9, 14), (9, 15), (10, 12), (10, 13), (10, 14), (10, 15), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 13), (12, 14), (12, 15), (12, 16), (12, 17), (13, 14), (13, 15), (13, 16), (13, 17), (14, 15), (14, 16), (14, 17), (14, 18)},
                    'last_season': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 16), (5, 17), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (9, 17), (10, 11), (10, 12), (10, 13), (10, 14), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (12, 16)},
                    'goals_condition': {(3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(4, 3), (4, 4), (4, 5), (4, 6), (5, 3), (5, 4), (5, 5), (5, 6), (6, 3), (6, 4), (6, 5), (6, 6), (7, 3), (7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 13), (12, 14), (12, 15), (12, 16), (12, 17), (13, 14), (13, 15), (13, 16), (13, 17), (14, 15), (14, 16), (14, 17), (14, 18)},
                    'last_season': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 16), (5, 17), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (9, 17), (10, 11), (10, 12), (10, 13), (10, 14), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (12, 16)},
                    'goals_condition': {(4, 5), (4, 6)},
                    'goals_latest': {(5, 4), (5, 5), (6, 3), (6, 4), (6, 5), (7, 3), (7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6) }
                },
                {
                    'current_rank': {(9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 13), (12, 14), (12, 15), (12, 16), (12, 17), (13, 14), (13, 15), (13, 16), (13, 17), (14, 15), (14, 16), (14, 17), (14, 18)},
                    'last_season': {(5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 16), (5, 17), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (9, 17), (10, 11), (10, 12), (10, 13), (10, 14), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (12, 16)},
                    'goals_condition': {(4, 7), (4, 8), (4, 9), (5, 5), (5, 6), (5, 7)},
                    'goals_latest': {(6, 4), (6, 5), (7, 4), (7, 5), (7, 6), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (2, 10), (2, 11), (2, 12), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(2, 1), (3, 1), (3, 2), (4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (10, 4), (11, 4)},
                    'goals_condition': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9)},
                    'goals_latest': {(7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (2, 10), (2, 11), (2, 12), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(3, 2), (4, 2), (4, 3), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (10, 4), (11, 4)},
                    'goals_condition': {(3, 2), (3, 3), (3, 4), (3, 5), (4, 3), (4, 4), (4, 5), (5, 3), (5, 4), (5, 5), (5, 6), (6, 4), (6, 5), (6, 6), (6, 7)},
                    'goals_latest': {(7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (2, 10), (2, 11), (2, 12), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(3, 2), (4, 2), (4, 3), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (10, 4), (11, 4)},
                    'goals_condition': {(7, 2), (7, 3), (7, 4)},
                    'goals_latest': {(9, 1), (9, 2), (9, 3)}
                },
                {
                    'current_rank': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (2, 10), (2, 11), (2, 12), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(2, 1), (3, 1), (3, 2), (4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (10, 4), (11, 4)},
                    'goals_condition': {(3, 6), (3, 7), (3, 8), (3, 9), (4, 6), (4, 7), (4, 8), (4, 9), (5, 6), (5, 7), (5, 8), (5, 9)},
                    'goals_latest': {(7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (6, 10), (6, 11), (6, 12), (7, 10), (7, 11), (7, 12), (8, 10), (8, 11), (8, 12)},
                    'last_season': {(2, 1), (3, 1), (3, 2), (4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (10, 4), (11, 4)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (3, 3), (4, 0), (4, 1), (4, 2), (4, 3), (5, 2), (5, 3)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (6, 10), (6, 11), (6, 12), (7, 10), (7, 11), (7, 12), (8, 10), (8, 11), (8, 12)},
                    'last_season': {(2, 1), (3, 1), (3, 2), (4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (10, 4), (11, 4)},
                    'goals_condition': {(2, 4), (2, 5), (2, 6)},
                    'goals_latest': {(3, 1), (3, 2), (3, 3), (4, 1), (4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (5, 5), (7, 3), (7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (6, 10), (6, 11), (6, 12), (7, 10), (7, 11), (7, 12), (8, 10), (8, 11), (8, 12)},
                    'last_season': {(2, 1), (3, 1), (3, 2), (4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (10, 4), (11, 4)},
                    'goals_condition': {(3, 3), (3, 4), (3, 5), (3, 6), (4, 4), (4, 5), (4, 6)},
                    'goals_latest': {(6, 0), (6, 1), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 0), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (6, 10), (6, 11), (6, 12), (7, 10), (7, 11), (7, 12), (8, 10), (8, 11), (8, 12)},
                    'last_season': {(2, 1), (3, 1), (3, 2), (4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (10, 4), (11, 4)},
                    'goals_condition': {(4, 7), (4, 8), (4, 9)},
                    'goals_latest': {(5, 3), (5, 4), (5, 5), (5, 6), (6, 4), (6, 5), (6, 6), (6, 7),(7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (6, 10), (6, 11), (6, 12), (7, 10), (7, 11), (7, 12), (8, 10), (8, 11), (8, 12)},
                    'last_season': {(2, 1), (3, 1), (3, 2), (4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (10, 4), (11, 4)},
                    'goals_condition': {(5, 6), (5, 7), (5, 8), (5, 9)},
                    'goals_latest': {(6, 4), (6, 5), (6, 6), (6, 7),(7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'last_season': {(6, 5), (7, 5), (7, 6), (8, 5), (8, 6), (9, 5), (9, 6), (10, 5), (10, 6), (11, 5), (11, 6), (12, 5), (12, 6), (13, 5), (14, 5), (15, 5)},
                    'goals_condition': {(2, 3), (2, 4)},
                    'goals_latest': {(4, 2), (4, 3), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'last_season': {(6, 5), (7, 5), (7, 6), (8, 5), (8, 6), (9, 5), (9, 6), (10, 5), (10, 6), (11, 5), (11, 6), (12, 5), (12, 6), (13, 5), (14, 5), (15, 5)},
                    'goals_condition': {(2, 5), (2, 6)},
                    'goals_latest': {(3, 1), (3, 2), (3, 3), (4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'last_season': {(6, 5), (7, 5), (7, 6), (8, 5), (8, 6), (9, 5), (9, 6), (10, 5), (10, 6), (11, 5), (11, 6), (12, 5), (12, 6)},
                    'goals_condition': {(3, 2), (3, 3), (3, 4), (3, 5), (3, 6)},
                    'goals_latest': {(4, 0), (4, 1), (4, 2), (4, 3), (5, 0), (5, 1), (5, 2), (5, 3), (6, 0), (6, 1), (6, 2), (6, 3), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                    'last_season': {(6, 5), (7, 5), (7, 6), (8, 5), (8, 6), (9, 5), (9, 6), (10, 5), (10, 6), (11, 5), (11, 6), (12, 5), (12, 6)},
                    'goals_condition': {(4, 3), (4, 4), (4, 5), (4, 6), (5, 3), (5, 4), (5, 5), (5, 6), (6, 3), (6, 4), (6, 5), (6, 6)},
                    'goals_latest': {(7, 1), (7, 2), (8, 1), (8, 2), (8, 3), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(1, 7), (1, 8), (1, 9), (2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15), (4, 16)},
                    'last_season': {(8, 7), (9, 7), (9, 8), (1, 69), (10, 11), (10, 8), (10, 9), (11, 10), (11, 7), (11, 8), (11, 9), (12, 10), (12, 11), (12, 7), (12, 8), (12, 9), (13, 10), (13, 11), (13, 12), (13, 7), (13, 8), (13, 9), (14, 10), (14, 11), (14, 12), (14, 13), (14, 7), (14, 8), (14, 9), (15, 10), (15, 11), (15, 12), (15, 13), (15, 14), (15, 7), (15, 8), (15, 9), (16, 10), (16, 12), (16, 13), (16, 14)},
                    'goals_condition': {(2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9)},
                    'goals_latest': {(3, 1), (3, 2), (4, 1), (4, 2), (5, 1), (5, 2), (5, 3), (6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(1, 7), (1, 8), (1, 9), (2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15), (4, 16)},
                    'last_season': {(8, 7), (9, 7), (9, 8), (11, 7), (12, 8), (13, 8), (14, 8), (15, 8), (10, 8), (10, 9), (11, 8), (11, 9), (12, 11), (12, 7), (13, 11), (13, 12), (13, 7), (14, 11), (14, 12), (14, 13), (14, 7), (15, 11), (15, 12), (15, 13), (15, 14), (15, 7), (16, 11), (16, 12), (16, 13), (16, 14)},
                    'goals_condition': {(1, 4), (1, 5)},
                    'goals_latest': {(3, 2), (3, 3), (4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5)}
                },
                {
                    'current_rank': {(3, 2), (4, 2), (4, 3), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 3), (8, 4), (9, 3), (9, 4), (10, 3), (10, 4), (11, 4)},
                    'last_season': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5), (2, 1), (2, 2), (2, 3), (2, 4)},
                    'goals_latest': {(3, 1), (3, 2), (3, 3), (4, 2), (4, 3), (4, 4), (5, 3), (5, 4), (5, 5), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(3, 2), (4, 2), (4, 3), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 3), (8, 4), (9, 3), (9, 4), (10, 3), (10, 4), (11, 4)},
                    'last_season': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'goals_condition': {(3, 1), (3, 2), (3, 3)},
                    'goals_latest': {(4, 0), (4, 1), (4, 2), (5, 0), (5, 1), (5, 2), (5, 3), (6, 0), (6, 1), (6, 2), (6, 3), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(3, 2), (4, 2), (4, 3), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 3), (8, 4), (9, 3), (9, 4), (10, 3), (10, 4), (11, 4)},
                    'last_season': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'goals_condition': {(3, 4), (3, 5), (3, 6), (3, 7)},
                    'goals_latest': {(6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(3, 2), (4, 2), (4, 3), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 3), (9, 4), (10, 3), (10, 4), (11, 4)},
                    'last_season': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'goals_condition': {(4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4)},
                    'goals_latest': {(7, 1), (7, 2), (8, 1), (8, 2), (9, 1), (9, 2)}
                },
                {
                    'current_rank': {(9, 7), (10, 7), (10, 8), (11, 7), (11, 8), (11, 9), (12, 10), (12, 11), (12, 9), (13, 10), (13, 11), (13, 12), (13, 9), (14, 10), (14, 9), (15, 10)},
                    'last_season': {(3, 5), (3, 6), (3, 7), (3, 8), (4, 5), (4, 6), (4, 7), (4, 8)},
                    'goals_condition': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9)},
                    'goals_latest': {(3, 2), (3, 3), (3, 4), (4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(4, 3), (5, 3), (5, 4), (6, 3), (6, 4), (7, 3), (7, 4), (8, 3), (8, 4), (9, 3), (9, 4), (10, 3), (10, 4), (11, 4)},
                    'last_season': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5), (2, 3), (2, 4), (2, 5), (2, 6), (3, 4), (3, 5), (3, 6), (4, 5), (4, 6)},
                    'goals_latest': {(5, 3), (5, 4), (5, 5), (6, 3), (6, 4), (6, 5), (6, 6), (7, 3), (7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(6, 5), (7, 5), (7, 6), (8, 5), (8, 6), (9, 5), (9, 6), (10, 5), (10, 6)},
                    'last_season': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (4, 5), (4, 6), (4, 7), (4, 8)},
                    'goals_condition': {(2, 4), (2, 5), (3, 4), (3, 5), (3, 6)},
                    'goals_latest': {(4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(6, 5), (7, 5), (7, 6), (8, 5), (8, 6), (9, 5), (9, 6), (10, 5), (10, 6)},
                    'last_season': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (4, 5), (4, 6), (4, 7), (4, 8)},
                    'goals_condition': {(3, 2), (3, 3), (4, 4), (4, 5), (4, 6), (5, 5), (5, 6), (6, 5), (6, 6)},
                    'goals_latest': {(6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(6, 5), (7, 5), (7, 6), (8, 5), (8, 6), (8, 7), (9, 5), (9, 6), (9, 7), (9, 8), (10, 5), (10, 6), (10, 7), (10, 8), (10, 9)},
                    'last_season': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5)},
                    'goals_latest': {(3, 2), (3, 3), (3, 4), (4, 1), (4, 2), (4, 3), (4, 4), (5, 1), (5, 2), (5, 3), (5, 4)}
                },
                {
                    'current_rank': {(6, 5), (7, 5), (7, 6), (8, 5), (8, 6), (8, 7), (9, 5), (9, 6), (9, 7), (9, 8), (10, 5), (10, 6), (10, 7), (10, 8), (10, 9)},
                    'last_season': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16)},
                    'goals_condition': {(2, 2), (2, 3)},
                    'goals_latest': {(4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (6, 0), (6, 1), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(6, 5), (7, 5), (7, 6), (8, 5), (8, 6), (8, 7), (9, 5), (9, 6), (9, 7), (9, 8), (10, 5), (10, 6), (10, 7), (10, 8), (10, 9)},
                    'last_season': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16)},
                    'goals_condition': {(2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (4, 5), (4, 6), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(6, 5), (7, 5), (7, 6), (8, 5), (8, 6), (8, 7), (9, 5), (9, 6), (9, 7), (9, 8), (10, 5), (10, 6), (10, 7), (10, 8), (10, 9)},
                    'last_season': {(5, 7), (5, 8), (5, 9), (6, 7), (6, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16)},
                    'goals_condition': {(3, 2), (3, 3), (3, 4), (3, 5), (3, 6), (3, 7), (4, 2), (4, 3), (4, 4), (4, 5), (4, 6), (4, 7)},
                    'goals_latest': {(6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(6, 4), (7, 6), (10, 6), (10, 7), (10, 9), (11, 10), (11, 6), (11, 7), (11, 9), (12, 10), (12, 11), (12, 6), (12, 7), (12, 9), (13, 10), (13, 11), (13, 12), (13, 7), (14, 10), (14, 11), (14, 12), (14, 13), (14, 9), (15, 10), (15, 11), (15, 12), (15, 13), (15, 14), (15, 9), (16, 10), (16, 11), (16, 12), (16, 13), (16, 14), (16, 15), (16, 9), (17, 15)},
                    'last_season': {(7, 12), (7, 13), (7, 14), (7, 15), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 12), (10, 13), (10, 14), (10, 15), (10, 16), (10, 17), (10, 18), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 14), (12, 15), (12, 16), (12, 17), (12, 18), (13, 14), (13, 15), (13, 16)},
                    'goals_condition': {(2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (3, 5)},
                    'goals_latest': {(4, 1), (4, 2), (4, 3), (4, 4), (5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(6, 4), (7, 6), (10, 6), (10, 7), (10, 9), (11, 10), (11, 6), (11, 7), (11, 9), (12, 10), (12, 11), (12, 6), (12, 7), (12, 9), (13, 10), (13, 11), (13, 12), (13, 7), (14, 10), (14, 11), (14, 12), (14, 13), (14, 9), (15, 10), (15, 11), (15, 12), (15, 13), (15, 14), (15, 9), (16, 10), (16, 11), (16, 12), (16, 13), (16, 14), (16, 15), (16, 9), (17, 15)},
                    'last_season': {(7, 12), (7, 13), (7, 14), (7, 15), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 12), (10, 13), (10, 14), (10, 15), (10, 16), (10, 17), (10, 18), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 14), (12, 15), (12, 16), (12, 17), (12, 18), (13, 14), (13, 15), (13, 16)},
                    'goals_condition': {(2, 7), (2, 8), (2, 9), (3, 6), (3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (4, 5), (4, 6), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(6, 4), (7, 6), (10, 6), (10, 7), (10, 9), (11, 10), (11, 6), (11, 7), (11, 9), (12, 10), (12, 11), (12, 60), (12, 70), (12, 9), (13, 10), (13, 11), (13, 12), (13, 7), (14, 10), (14, 11), (14, 12), (14, 13), (14, 9), (15, 10), (15, 11), (15, 12), (15, 13), (15, 14), (15, 9), (16, 10), (16, 11), (16, 12), (16, 13), (16, 14), (16, 15), (16, 9), (17, 15)},
                    'last_season': {(7, 12), (7, 13), (7, 14), (7, 15), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 12), (10, 13), (10, 14), (10, 15), (10, 16), (10, 17), (10, 18), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 14), (12, 15), (12, 16), (12, 17), (12, 18), (13, 15), (13, 16)},
                    'goals_condition': {(4, 6), (4, 7), (4, 8), (4, 9), (5, 6), (5, 7), (5, 8), (5, 9)},
                    'goals_latest': {(7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(7, 6), (8, 6), (9, 6), (10, 6), (11, 6), (12, 6)},
                    'last_season': {(11, 5), (10, 5), (9, 5), (8, 5), (7, 5), (12, 6), (11, 6), (10, 6), (9, 6), (8, 6), (7, 6), (11, 8), (10, 8), (9, 8), (13, 9), (12, 9), (11, 9), (10, 9), (15, 10), (15, 11), (15, 12), (15, 13)},
                    'goals_condition': {(1, 1), (1, 2), (1, 3), (1, 4)},
                    'goals_latest': {(2, 0), (2, 1), (2, 2), (3, 0), (3, 1), (3, 2), (3, 3), (4, 0), (4, 1), (4, 2), (4, 3), (5, 2), (5, 3), (5, 4)}
                },
                {
                    'current_rank': {(7, 6), (8, 6), (9, 6), (10, 6), (11, 6), (12, 6)},
                    'last_season': {(11, 5), (10, 5), (9, 5), (8, 5), (7, 5), (12, 6), (11, 6), (10, 6), (9, 6), (8, 6), (7, 6), (11, 8), (10, 8), (9, 8), (13, 9), (12, 9), (11, 9), (10, 9), (15, 10), (15, 11), (15, 12), (15, 13)},
                    'goals_condition': {(2, 2), (2, 3), (2, 4), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4)}
                },
                {
                    'current_rank': {(7, 6), (8, 6), (9, 6), (10, 6), (11, 6), (12, 6)},
                    'last_season': {(11, 5), (10, 5), (9, 5), (8, 5), (7, 5), (12, 6), (11, 6), (10, 6), (9, 6), (8, 6), (7, 6), (11, 8), (10, 8), (9, 8), (13, 9), (12, 9), (11, 9), (10, 9), (15, 10), (15, 11), (15, 12), (15, 13)},
                    'goals_condition': {(4, 4), (4, 5), (4, 6), (4, 7)},
                    'goals_latest': {(5, 0), (5, 1), (5, 2), (5, 3), (6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(7, 6), (8, 6), (9, 6), (10, 6), (11, 6), (12, 6)},
                    'last_season': {(11, 5), (10, 5), (9, 5), (8, 5), (7, 5), (12, 6), (11, 6), (10, 6), (9, 6), (8, 6), (7, 6), (11, 8), (10, 8), (9, 8), (13, 9), (12, 9), (11, 9), (10, 9), (15, 10), (15, 11), (15, 12), (15, 13)},
                    'goals_condition': {(5, 3), (5, 4), (5, 5), (5, 6), (5, 7)},
                    'goals_latest': {(6, 1), (6, 2), (6, 3), (7, 1), (7, 2), (7, 3), (8, 1), (8, 2), (8, 3), (9, 1), (9, 2), (9, 3)}
                },
                {
                    'current_rank': {(13, 7), (12, 7), (11, 7), (10, 7), (9, 7)},
                    'last_season': {(6, 2), (5, 2), (4, 2), (8, 3), (7, 3), (6, 3), (5, 3), (8, 4), (7, 4), (6, 4), (5, 4)},
                    'goals_condition': {(3, 1), (3, 2), (3, 3), (4, 1), (4, 2), (4, 3), (4, 4)},
                    'goals_latest': {(6, 0), (6, 1), (6, 2), (6, 3), (6, 4), (7, 0), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(13, 7), (12, 7), (11, 7), (10, 7), (9, 7)},
                    'last_season': {(6, 2), (5, 2), (4, 2), (8, 3), (7, 3), (6, 3), (5, 3), (8, 4), (7, 4), (6, 4), (5, 4)},
                    'goals_condition': {(3, 4), (3, 5), (3, 6)},
                    'goals_latest': {(5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(12, 8), (11, 8), (10, 8), (9, 8)},
                    'last_season': {(6, 2), (5, 2), (4, 2), (9, 3), (8, 3), (7, 3), (6, 3), (5, 3), (8, 4), (7, 4), (6, 4), (5, 4), (4, 1), (3, 1)},
                    'goals_condition': {(3, 3), (3, 4), (3, 5), (3, 6), (3, 7), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(12, 8), (11, 8), (10, 8), (9, 8)},
                    'last_season': {(6, 2), (5, 2), (4, 2), (9, 3), (8, 3), (7, 3), (6, 3), (5, 3), (8, 4), (7, 4), (6, 4), (5, 4), (4, 1), (3, 1)},
                    'goals_condition': {(4, 4), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9)},
                    'goals_latest': {(5, 2), (5, 3), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(16, 8), (15, 8), (14, 8), (13, 8), (12, 8), (11, 8), (10, 8), (9, 8)},
                    'last_season': {(11, 5), (10, 5), (9, 5), (8, 5), (7, 5), (12, 6), (11, 6), (11, 10), (10, 6), (9, 6), (8, 6), (7, 6), (12, 8), (11, 8), (10, 9), (10, 8), (9, 8), (15, 9), (14, 9), (13, 9), (12, 9), (11, 9), (10, 9), (15, 10), (15, 11), (15, 12), (15, 13), (16, 11), (14, 10), (12, 10)},
                    'goals_condition': {(0, 5), (0, 6), (2, 4), (2, 5), (2, 6), (2, 7), (3, 5), (3, 6), (3, 7)},
                    'goals_latest': {(3, 2), (3, 3), (3, 4), (4, 2), (4, 3), (4, 4), (4, 5), (5, 3), (5, 4), (5, 5), (6, 3), (6, 4), (6, 5), (6, 6), (7, 4), (7, 5), (7, 6)}
                },
                {
                    'current_rank': {(16, 8), (15, 8), (14, 8), (13, 8), (12, 8), (11, 8), (10, 8), (9, 8)},
                    'last_season': {(11, 5), (10, 5), (9, 5), (8, 5), (7, 5), (12, 6), (11, 6), (11, 10), (10, 6), (9, 6), (8, 6), (7, 6), (12, 8), (11, 8), (10, 9), (10, 8), (9, 8), (15, 9), (14, 9), (13, 9), (12, 9), (11, 9), (10, 9), (15, 10), (15, 11), (15, 12), (15, 13), (16, 11), (14, 10), (12, 10)},
                    'goals_condition': {(4, 4), (4, 5), (5, 4), (5, 5), (4, 6)},
                    'goals_latest': {(6, 4), (6, 5), (6, 6), (7, 4), (7, 5), (7, 6), (8, 4), (8, 5), (8, 6), (9, 4), (9, 5), (9, 6), (9, 7)}
                },
                {
                    'current_rank': {(16, 8), (15, 8), (14, 8), (13, 8), (12, 8), (11, 8), (10, 8), (9, 8)},
                    'last_season': {(11, 5), (10, 5), (9, 5), (8, 5), (7, 5), (12, 6), (11, 6), (11, 10), (10, 6), (9, 6), (8, 6), (7, 6), (12, 8), (11, 8), (10, 9), (10, 8), (9, 8), (15, 9), (14, 9), (13, 9), (12, 9), (11, 9), (10, 9), (15, 10), (15, 11), (15, 12), (15, 13), (16, 11), (14, 10), (12, 10)},
                    'goals_condition': {(7, 2), (7, 3)},
                    'goals_latest': {(9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(14, 10), (13, 10), (12, 10), (11, 10), (9, 10), (14, 11), (13, 11), (12, 11), (14, 12), (13, 12)},
                    'last_season': {(12, 5), (11, 5), (10, 5), (9, 5), (8, 5), (7, 5), (6, 5), (10, 4), (9, 4), (8, 4), (7, 4), (6, 4), (5, 4)},
                    'goals_condition': {(2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(4, 3), (4, 4), (4, 5), (4, 6), (5, 3), (5, 4), (5, 5), (5, 6), (6, 4), (6, 5), (6, 6), (6, 7),(7, 4), (7, 5), (7, 6), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(14, 10), (13, 10), (12, 10), (11, 10), (9, 10), (14, 11), (13, 11), (12, 11), (14, 12), (13, 12)},
                    'last_season': {(12, 5), (11, 5), (10, 5), (9, 5), (8, 5), (7, 5), (6, 5), (10, 4), (9, 4), (8, 4), (7, 4), (6, 4), (5, 4)},
                    'goals_condition': {(3, 4), (3, 5), (3, 6), (4, 6), (4, 7), (4, 8), (4, 9)},
                    'goals_latest': {(6, 3), (6, 4), (6, 5), (7, 3), (7, 4), (7, 5), (8, 3), (8, 4), (8, 5), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(14, 10), (13, 10), (12, 10), (11, 10), (9, 10), (14, 11), (13, 11), (12, 11), (14, 12), (13, 12)},
                    'last_season': {(14, 7), (15, 7), (13, 7), (12, 7), (14, 8), (15, 8), (13, 8), (12, 8), (15, 9), (11, 8), (15, 7), (14, 7), (13, 7), (12, 7), (11, 7), (15, 9), (14, 9), (13, 9), (12, 9), (11, 9)},
                    'goals_condition': {(1, 3), (1, 4), (1, 5), (1, 6)},
                    'goals_latest': {(2, 2), (2, 3), (2, 4), (3, 2), (3, 3), (3, 4), (3, 5), (4, 4), (4, 5), (4, 6), (5, 4), (5, 5), (5, 6), (6, 4), (6, 5), (6, 6)}
                },
                {
                    'current_rank': {(2, 11), (2, 12), (2, 10), (2, 9), (2, 8), (2, 7), (3, 12), (3, 11), (3, 10), (3, 8), (3, 9), (3, 7), (3, 2), (4, 12), (4, 11), (4, 10), (4, 9), (4, 8), (4, 7), (5, 4), (5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 4), (6, 5), (6, 7), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 6), (7, 8), (7, 9), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 7), (8, 9), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 8), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 9), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (10, 16), (11, 13), (11, 14), (11, 15), (11, 16)},
                    'last_season': {(80, 80)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5), (1, 6)},
                    'goals_latest': {(5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5)}
                },
                {
                    'current_rank': {(2, 11), (2, 12), (2, 10), (2, 9), (2, 8), (2, 7), (3, 12), (3, 11), (3, 10), (3, 8), (3, 9), (3, 7), (3, 2), (4, 12), (4, 11), (4, 10), (4, 9), (4, 8), (4, 7), (5, 4), (5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 4), (6, 5), (6, 7), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 6), (7, 8), (7, 9), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 7), (8, 9), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 8), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 9), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (10, 16), (11, 13), (11, 14), (11, 15), (11, 16)},
                    'last_season': {(80, 80)},
                    'goals_condition': {(2, 1), (2, 2), (2, 3), (2, 4), (2, 5)},
                    'goals_latest': {(4, 1), (4, 2), (5, 0), (5, 1), (5, 2), (6, 0), (6, 1), (6, 2), (7, 0), (7, 1), (7, 2)}
                },
                {
                    'current_rank': {(2, 11), (2, 12), (2, 10), (2, 9), (2, 8), (2, 7), (3, 12), (3, 11), (3, 10), (3, 8), (3, 9), (3, 7), (3, 2), (4, 12), (4, 11), (4, 10), (4, 9), (4, 8), (4, 7), (5, 4), (5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 4), (6, 5), (6, 7), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 6), (7, 8), (7, 9), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 7), (8, 9), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 8), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 9), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (10, 16), (11, 13), (11, 14), (11, 15), (11, 16)},
                    'last_season': {(80, 80)},
                    'goals_condition': {(3, 1), (3, 2), (3, 3), (3, 4), (4, 4), (4, 5)},
                    'goals_latest': {(6, 0), (6, 1), (6, 2), (6, 3), (7, 0), (7, 1), (7, 2), (7, 3), (8, 1), (8, 2), (8, 3), (9, 1), (9, 2), (9, 3)}
                },
                {
                    'current_rank': {(2, 11), (2, 12), (2, 10), (2, 9), (2, 8), (2, 7), (3, 12), (3, 11), (3, 10), (3, 8), (3, 9), (3, 7), (3, 2), (4, 12), (4, 11), (4, 10), (4, 9), (4, 8), (4, 7), (5, 4), (5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 4), (6, 5), (6, 7), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 6), (7, 8), (7, 9), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 7), (8, 9), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 8), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 9), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (10, 16), (11, 13), (11, 14), (11, 15), (11, 16)},
                    'last_season': {(80, 80)},
                    'goals_condition': {(2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 6), (4, 7), (4, 8), (4, 9)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (5, 1), (5, 2), (5, 3), (6, 1), (6, 2), (6, 3), (7, 1), (7, 2), (7, 3), (8, 2), (8, 3), (9, 1), (9, 2), (9, 3)}
                },
                {
                    'current_rank': {(7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (7, 16), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16)},
                    'last_season': {(80, 9), (80, 10), (80, 11), (80, 12), (80, 13), (80, 14)},
                    'goals_condition': {(1, 4), (1, 5), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (7, 3), (7, 4), (7, 5), (8, 3), (8, 4), (8, 5), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(7, 4), (8, 4), (7, 5), (8, 5), (7, 6), (8, 6), (9, 6), (8, 7), (9, 7), (10, 7), (9, 8), (10, 8), (11, 8), (10, 9), (11, 9), (11, 10), (12, 10), (12, 11), (13, 11), (13, 12), (14, 12), (15, 12)},
                    'last_season': {(80, 9), (80, 10), (80, 11), (80, 12), (80, 13), (80, 14)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5), (2, 2), (2, 3), (2, 4), (2, 5), (3, 3), (3, 4), (3, 5), (3, 6)},
                    'goals_latest': {(5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 12), (10, 13), (10, 14), (10, 15), (11, 13), (11, 14), (11, 15), (12, 14), (12, 15), (13, 15)},
                    'last_season': {(80, 9), (80, 10), (80, 11), (80, 12), (80, 13), (80, 14), (80, 15), (80, 16)},
                    'goals_condition': {(0, 5), (0, 6), (0, 7), (0, 8), (1, 2), (1, 3), (1, 4), (1, 5), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8)},
                    'goals_latest': {(3, 2), (3, 3), (3, 4), (3, 5), (4, 3), (4, 4), (4, 5), (4, 6), (5, 3), (5, 4), (5, 5), (5, 6), (6, 3), (6, 4), (6, 5), (6, 6), (7, 3), (7, 4), (7, 5), (7, 6)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 7), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14)},
                    'last_season': {(80, 9), (80, 10), (80, 11), (80, 12), (80, 13), (80, 14)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5)},
                    'goals_latest': {(2, 1), (2, 2), (2, 3), (3, 2), (3, 3), (4, 2), (4, 3), (4, 4), (4, 5), (5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 7), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14)},
                    'last_season': {(80, 9), (80, 10), (80, 11), (80, 12), (80, 13), (80, 14)},
                    'goals_condition': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (4, 5), (5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5)}
                },
                {
                    'current_rank': {(1, 9), (1, 8), (1, 10), (1, 11), (1, 12), (2, 11), (2, 12), (2, 10), (2, 9), (2, 8), (3, 12), (3, 11), (3, 10), (3, 8), (3, 9), (4, 12), (4, 11), (4, 10), (4, 9), (4, 8)},
                    'last_season': {(80, 9), (80, 10), (80, 11), (80, 12), (80, 13), (80, 14)},
                    'goals_condition': {(2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (3, 5), (3, 6)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(1, 9), (1, 8), (1, 10), (1, 11), (1, 12), (2, 11), (2, 12), (2, 10), (2, 9), (2, 8), (3, 12), (3, 11), (3, 10), (3, 8), (3, 9), (4, 12), (4, 11), (4, 10), (4, 9), (4, 8)},
                    'last_season': {(80, 9), (80, 10), (80, 11), (80, 12), (80, 13), (80, 14)},
                    'goals_condition': {(3, 2), (3, 3), (3, 4), (4, 2), (4, 3), (4, 4), (4, 5), (4, 6), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6)},
                    'goals_latest': {(6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15)},
                    'last_season': {(80, 3), (80, 4), (80, 5), (80, 6), (80, 7), (80, 8)},
                    'goals_condition': {(1, 4), (1, 5)},
                    'goals_latest': {(2, 3), (2, 4), (2, 5), (3, 3), (3, 4), (3, 5), (4, 3), (4, 4), (4, 5), (5, 3), (5, 4), (5, 5), (6, 4), (6, 5)}
                },
                {
                    'current_rank': {(7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15)},
                    'last_season': {(80, 3), (80, 4), (80, 5), (80, 6), (80, 7), (80, 8)},
                    'goals_condition': {(2, 6), (2, 7), (2, 8), (3, 6), (3, 7), (3, 8), (3, 9), (4, 6), (4, 7), (4, 8), (4, 9)},
                    'goals_latest': {(5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15)},
                    'last_season': {(80, 3), (80, 4), (80, 5), (80, 6), (80, 7), (80, 8)},
                    'goals_condition': {(2, 4), (2, 5), (3, 3), (3, 4), (3, 5), (4, 5)},
                    'goals_latest': {(5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(7, 4), (8, 4), (7, 5), (8, 5), (7, 6), (8, 6), (9, 6), (8, 7), (9, 7), (10, 7), (9, 8), (10, 8), (11, 8), (10, 9), (11, 9), (11, 10), (12, 10), (12, 11), (13, 11), (13, 12), (14, 12), (15, 12)},
                    'last_season': {(80, 3), (80, 4), (80, 5), (80, 6), (80, 7), (80, 8)},
                    'goals_condition': {(1, 4), (1, 5)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (4, 5), (5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5)}
                },
                {
                    'current_rank': {(7, 4), (8, 4), (7, 5), (8, 5), (7, 6), (8, 6), (9, 6), (8, 7), (9, 7), (10, 7), (9, 8), (10, 8), (11, 8), (10, 9), (11, 9), (11, 10), (12, 10), (12, 11), (13, 11), (13, 12), (14, 12), (15, 12)},
                    'last_season': {(80, 3), (80, 4), (80, 5), (80, 6), (80, 7), (80, 8)},
                    'goals_condition': {(2, 4), (2, 5), (2, 6), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(4, 3), (4, 4), (4, 5), (4, 6), (5, 3), (5, 4), (5, 5), (5, 6), (6, 4), (6, 5), (6, 6)}
                },
                {
                    'current_rank': {(7, 4), (8, 4), (7, 5), (8, 5), (7, 6), (8, 6), (9, 6), (8, 7), (9, 7), (10, 7), (9, 8), (10, 8), (11, 8), (10, 9), (11, 9), (11, 10), (12, 10), (12, 11), (13, 11), (13, 12), (14, 12), (15, 12)},
                    'last_season': {(80, 3), (80, 4), (80, 5), (80, 6), (80, 7), (80, 8)},
                    'goals_condition': {(2, 3), (2, 4), (3, 2), (3, 3), (3, 4), (4, 2), (4, 3), (4, 4), (5, 5), (5, 6), (5, 7), (5, 8), (5, 9)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(7, 4), (8, 4), (7, 5), (8, 5), (7, 6), (8, 6), (9, 6), (8, 7), (9, 7), (10, 7), (9, 8), (10, 8), (11, 8), (10, 9), (11, 9), (11, 10), (12, 10), (12, 11), (13, 11), (13, 12), (14, 12), (15, 12)},
                    'last_season': {(80, 3), (80, 4), (80, 5), (80, 6), (80, 7), (80, 8)},
                    'goals_condition': {(4, 5), (4, 6), (4, 7), (4, 8), (4, 9)},
                    'goals_latest': {(5, 3), (5, 4), (5, 5), (6, 3), (6, 4), (6, 5), (7, 3), (7, 4), (7, 5), (8, 3), (8, 4), (8, 5), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14)},
                    'last_season': {(80, 3), (80, 4), (80, 5), (80, 6), (80, 7), (80, 8)},
                    'goals_condition': {(1, 3), (1, 4), (1, 5), (1, 6), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (3, 3), (4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (5, 1), (5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5)}
                },
                {
                    'current_rank': {(1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (3, 5), (3, 6), (3, 7), (3, 8), (4, 5), (4, 6), (4, 7), (4, 8)},
                    'last_season': {(80, 3), (80, 4), (80, 5), (80, 6), (80, 7), (80, 8)},
                    'goals_condition': {(2, 3), (2, 4), (2, 5), (2, 6), (3, 4), (3, 5), (3, 6)},
                    'goals_latest': {(4, 2), (4, 3), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 9), (2, 10), (2, 11), (2, 12), (2, 13), (3, 9), (3, 10), (3, 11), (3, 12), (3, 13), (4, 9), (4, 10), (4, 11), (4, 12), (4, 13)},
                    'last_season': {(80, 3), (80, 4), (80, 5), (80, 6), (80, 7), (80, 8)},
                    'goals_condition': {(2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(5, 1), (5, 2), (5, 3), (6, 1), (6, 2), (6, 3), (7, 2), (7, 3), (8, 1), (8, 2), (8, 3), (9, 1), (9, 2), (9, 3)}
                },
                {
                    'current_rank': {(9, 12), (9, 13), (9, 14), (9, 15), (10, 12), (10, 13), (10, 14)},
                    'last_season': {(9, 80), (10, 80), (11, 80), (12, 80), (13, 80), (14, 80)},
                    'goals_condition': {(3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(6, 3), (6, 4), (6, 5), (6, 6), (6, 7),(7, 3), (7, 4), (7, 5), (7, 6), (7, 7), (8, 3), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(10, 8), (11, 8), (12, 8), (10, 9), (11, 9), (12, 9), (11, 10), (12, 10), (13, 10), (12, 11), (13, 11), (13, 12), (14, 12), (15, 12)},
                    'last_season': {(9, 80), (10, 80), (11, 80), (12, 80), (13, 80), (14, 80)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (2, 4), (2, 5), (2, 6)},
                    'goals_latest': {(5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (8, 3), (8, 4), (8, 5), (8, 6),(9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(10, 8), (11, 8), (12, 8), (10, 9), (11, 9), (12, 9), (11, 10), (12, 10), (13, 10), (12, 11), (13, 11), (13, 12), (14, 12), (15, 12)},
                    'last_season': {(9, 80), (10, 80), (11, 80), (12, 80), (13, 80), (14, 80)},
                    'goals_condition': {(2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(4, 4), (4, 5), (4, 6), (4, 7), (5, 4), (5, 5), (5, 6), (5, 7), (6, 4), (6, 5), (6, 6), (6, 7),(7, 4), (7, 5), (7, 6), (8, 4), (8, 5), (8, 6), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(10, 8), (11, 8), (12, 8), (10, 9), (11, 9), (12, 9), (11, 10), (12, 10), (13, 10), (12, 11), (13, 11), (13, 12), (14, 12), (15, 12)},
                    'last_season': {(9, 80), (10, 80), (11, 80), (12, 80), (13, 80), (14, 80)},
                    'goals_condition': {(3, 5), (3, 6), (4, 5), (4, 6), (4, 7), (5, 5), (5, 6), (5, 7)},
                    'goals_latest': {(6, 3), (6, 4), (6, 5), (6, 6), (7, 3), (7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(7, 9), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15)},
                    'last_season': {(9, 80), (10, 80), (11, 80), (12, 80), (13, 80), (14, 80)},
                    'goals_condition': {(3, 2), (3, 3), (3, 4), (4, 2), (4, 3), (4, 4), (5, 3), (5, 4), (6, 3), (6, 4)},
                    'goals_latest': {(8, 0), (8, 1), (8, 2), (8, 3), (9, 0), (9, 1), (9, 2), (9, 3)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (5, 17), (6, 7), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15)},
                    'last_season': {(9, 80), (10, 80), (11, 80), (12, 80), (13, 80), (14, 80)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5), (2, 3), (2, 4), (2, 5), (2, 6), (3, 5), (3, 6)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (3, 3), (4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (4, 5), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (6, 3), (6, 4), (6, 5), (6, 6), (6, 7),(7, 3), (7, 4), (7, 5), (7, 6), (8, 4), (8, 5), (8, 6), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (5, 17), (6, 7), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15)},
                    'last_season': {(9, 80), (10, 80), (11, 80), (12, 80), (13, 80), (14, 80)},
                    'goals_condition': {(3, 3), (3, 4)},
                    'goals_latest': {(5, 2), (5, 3), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(10, 12), (10, 13), (10, 14), (10, 15), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (12, 14), (12, 15), (12, 16), (12, 17)},
                    'last_season': {(5, 80), (6, 80), (7, 80), (8, 80)},
                    'goals_condition': {(1, 4), (1, 5), (1, 6), (2, 4), (2, 5), (2, 6)},
                    'goals_latest': {(3, 2), (3, 3), (3, 4), (3, 5), (4, 3), (4, 4), (4, 5), (4, 6), (5, 3), (5, 4), (5, 5), (5, 6), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(10, 12), (10, 13), (10, 14), (10, 15), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (12, 14), (12, 15), (12, 16), (12, 17)},
                    'last_season': {(5, 80), (6, 80), (7, 80), (8, 80)},
                    'goals_condition': {(2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (5, 5), (5, 6), (5, 7), (5, 8)},
                    'goals_latest': {(6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(10, 6), (10, 7), (10, 8), (10, 9), (11, 6), (11, 7), (11, 8), (11, 9), (12, 8), (12, 9), (11, 9), (12, 9), (13, 9), (11, 10), (12, 11), (13, 10), (13, 11), (13, 12), (14, 10), (14, 11), (14, 12), (14, 13), (15, 10), (15, 11), (15, 12), (15, 13), (15, 14)},
                    'last_season': {(5, 80), (6, 80), (7, 80), (8, 80)},
                    'goals_condition': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (3, 5), (3, 6), (4, 5), (4, 6)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (5, 3), (5, 4), (5, 5), (6, 3), (6, 4), (6, 5), (6, 6), (7, 3), (7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (8, 6),(9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(10, 6), (10, 7), (10, 8), (10, 9), (11, 6), (11, 7), (11, 8), (11, 9), (12, 8), (12, 9), (11, 9), (12, 9), (13, 9), (11, 10), (12, 11), (13, 10), (13, 11), (13, 12), (14, 10), (14, 11), (14, 12), (14, 13), (15, 10), (15, 11), (15, 12), (15, 13), (15, 14)},
                    'last_season': {(5, 80), (6, 80), (7, 80), (8, 80)},
                    'goals_condition': {(3, 3), (3, 4), (4, 4), (5, 4), (5, 5), (5, 6)},
                    'goals_latest': {(6, 3), (6, 4), (6, 5), (7, 3), (7, 4), (7, 5), (8, 3), (8, 4), (8, 5), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14)},
                    'last_season': {(5, 80), (6, 80), (7, 80), (8, 80)},
                    'goals_condition': {(2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 6), (4, 7), (4, 8), (4, 9)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (5, 1), (5, 2), (5, 3), (6, 1), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14)},
                    'last_season': {(5, 80), (6, 80), (7, 80), (8, 80)},
                    'goals_condition': {(3, 3), (3, 4), (4, 4), (4, 5)},
                    'goals_latest': {(5, 0), (5, 1), (5, 2), (6, 0), (6, 1), (6, 2), (6, 3), (7, 1), (7, 2), (7, 3), (8, 1), (8, 2), (8, 3), (9, 1), (9, 2), (9, 3)}
                },
                {
                    'current_rank': {(5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16)},
                    'last_season': {(5, 80), (6, 80), (7, 80), (8, 80)},
                    'goals_condition': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7)},
                    'goals_latest': {(3, 2), (3, 3), (4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (5, 5), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6)}
                },
                {
                    'current_rank': {(5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16)},
                    'last_season': {(5, 80), (6, 80), (7, 80), (8, 80)},
                    'goals_condition': {(3, 3), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (5, 5), (6, 3), (6, 4), (6, 5), (6, 6), (7, 3), (7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16)},
                    'last_season': {(5, 80), (6, 80), (7, 80), (8, 80)},
                    'goals_condition': {(4, 5), (4, 6), (4, 7), (4, 8), (4, 9)},
                    'goals_latest': {(6, 4), (6, 5), (6, 6), (6, 7),(7, 4), (7, 5), (7, 6), (7, 7), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (8, 7), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(1, 6), (1, 7), (1, 8), (1, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 11), (2, 12), (2, 13), (2, 6), (2, 7), (2, 8), (2, 9), (3, 6), (3, 7), (3, 8), (3, 9), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(5, 80), (6, 80), (7, 80), (8, 80)},
                    'goals_condition': {(2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (3, 4), (3, 5), (3, 6)},
                    'goals_latest': {(4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 3), (6, 1), (6, 2), (6, 3), (7, 2), (7, 3), (8, 1), (8, 2), (8, 3), (9, 1), (9, 2), (9, 3)}
                },
                {
                    'current_rank': {(1, 6), (1, 7), (1, 8), (1, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 11), (2, 12), (2, 13), (2, 6), (2, 7), (2, 8), (2, 9), (3, 6), (3, 7), (3, 8), (3, 9), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (2, 10), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(5, 80), (6, 80), (7, 80), (8, 80)},
                    'goals_condition': {(5, 5), (5, 6), (6, 5), (6, 6)},
                    'goals_latest': {(7, 1), (7, 2), (7, 3), (8, 1), (8, 2), (8, 3), (9, 1), (9, 2), (9, 3)}
                },
                {
                    'current_rank': {(5, 6), (5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 8), (7, 9), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (7, 16), (8, 9), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15)},
                    'last_season': {(2, 80), (3, 80), (4, 80)},
                    'goals_condition': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7)},
                    'goals_latest': {(4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(5, 6), (5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (7, 8), (7, 9), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (7, 16), (8, 9), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15)},
                    'last_season': {(2, 80), (3, 80), (4, 80)},
                    'goals_condition': {(3, 1), (3, 2), (3, 3)},
                    'goals_latest': {(6, 2), (6, 3), (6, 4), (6, 5), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (1, 14), (2, 10), (2, 11), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(2, 80), (3, 80), (4, 80)},
                    'goals_condition': {(2, 0), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9)},
                    'goals_latest': {(5, 0), (5, 1), (5, 2), (5, 3), (6, 0), (6, 1), (6, 2), (6, 3), (7, 1), (7, 2), (7, 3), (8, 1), (8, 2), (8, 3), (9, 1), (9, 2), (9, 3)}
                },
                {
                    'current_rank': {(7, 8), (7, 9), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 9), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14)},
                    'last_season': {(8, 90), (9, 90), (10, 90), (11, 90)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5)},
                    'goals_latest': {(3, 1), (3, 2), (3, 3), (4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 3), (5, 4)}
                },
                {
                    'current_rank': {(11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 14), (12, 15), (12, 16), (12, 17), (12, 18), (13, 15), (13, 16), (13, 17), (13, 18), (14, 15), (14, 16), (14, 17), (14, 18)},
                    'last_season': {(90, 3), (90, 4), (90, 5), (90, 6), (90, 7), (90, 8), (90, 9)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5)},
                    'goals_latest': {(3, 1), (3, 2), (3, 3), (4, 1), (4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4)}
                },
                {
                    'current_rank': {(8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 12), (10, 13), (10, 14), (10, 15), (10, 16), (10, 17), (10, 18), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (11, 19), (11, 20), (12, 14), (12, 15), (12, 16), (12, 17), (12, 18), (12, 19), (12, 20), (13, 15), (13, 16), (13, 17), (13, 18), (13, 19), (13, 20), (14, 15), (14, 16), (14, 17), (14, 18)},
                    'last_season': {(8, 90), (9, 90), (10, 90)},
                    'goals_condition': {(2, 4), (2, 5), (2, 6), (2, 7), (2, 8)},
                    'goals_latest': {(3, 2), (3, 3), (3, 4), (4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (6, 5)}
                },
                {
                    'current_rank': {(10, 9), (11, 6), (11, 7), (11, 8), (11, 9), (12, 9), (11, 9), (12, 9), (13, 9), (11, 10), (12, 11), (13, 10), (13, 11), (13, 12), (14, 10), (14, 11), (14, 12), (14, 13), (15, 10), (15, 11), (15, 12), (15, 13), (15, 14)},
                    'last_season': {(8, 90), (9, 90), (10, 90)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5)},
                    'goals_latest': {(3, 1), (3, 2), (3, 3), (4, 1), (4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4)}
                },
                {
                    'current_rank': {(10, 6), (10, 7), (10, 8), (10, 9), (11, 6), (11, 7), (11, 8), (11, 9), (12, 8), (12, 9)},
                    'last_season': {(3, 90), (4, 90), (5, 90), (6, 90), (7, 90)},
                    'goals_condition': {(3, 2), (3, 3), (3, 4), (4, 2), (4, 3), (4, 4)},
                    'goals_latest': {(6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(10, 6), (10, 7), (10, 8), (10, 9), (11, 6), (11, 7), (11, 8), (11, 9), (12, 8), (12, 9)},
                    'last_season': {(3, 90), (4, 90), (5, 90), (6, 90), (7, 90)},
                    'goals_condition': {(5, 4), (5, 5), (5, 6), (6, 5), (6, 6), (6, 7)},
                    'goals_latest': {(7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14)},
                    'last_season': {(3, 90), (4, 90), (5, 90), (6, 90), (7, 90)},
                    'goals_condition': {(3, 4), (3, 5), (3, 6), (4, 5), (4, 6), (4, 7)},
                    'goals_latest': {(6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(7, 4), (7, 5), (8, 4), (8, 5), (9, 5), (9, 6), (9, 7)},
                    'last_season': {(3, 90), (4, 90), (5, 90), (6, 90), (7, 90)},
                    'goals_condition': {(3, 3), (3, 4), (3, 5), (3, 6), (3, 7), (4, 3), (4, 4), (4, 5), (4, 6), (4, 7)},
                    'goals_latest': {(7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14)},
                    'last_season': {(8, 90), (9, 90), (10, 90), (11, 90), (12, 90), (13, 90)},
                    'goals_condition': {(1, 3), (1, 4), (1, 5), (2, 4), (2, 5), (2, 6), (3, 4), (3, 5), (3, 6)},
                    'goals_latest': {(2, 1), (2, 2), (2, 3), (3, 2), (3, 3), (3, 4), (3, 5), (4, 2), (4, 3), (4, 4), (5, 3), (5, 4), (5, 5), (6, 3), (6, 4), (6, 5), (7, 3), (7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(1, 10), (1, 11), (1, 9), (1, 8), (1, 7), (2, 11), (2, 10), (2, 9), (2, 8), (2, 7), (3, 12), (3, 13), (3, 14), (3, 11), (3, 10), (3, 8), (3, 9), (3, 7), (4, 14), (4, 13), (4, 12), (4, 11), (4, 10), (4, 9), (4, 8), (4, 7)},
                    'last_season': {(8, 90), (9, 90), (10, 90)},
                    'goals_condition': {(4, 6), (4, 7), (5, 5), (5, 6), (5, 7), (6, 6), (6, 5), (6, 7)},
                    'goals_latest': {(7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 7), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14)},
                    'last_season': {(90, 10), (90, 11), (90, 12), (90, 13), (90, 14), (90, 15), (90, 16), (90, 17), (90, 18)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5), (2, 4), (2, 5), (2, 6), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(4, 1), (4, 2), (4, 3), (4, 4), (5, 1), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 10), (1, 11), (1, 12), (2, 11), (2, 10), (2, 12), (2, 13), (2, 14), (3, 15), (3, 16), (3, 13), (3, 14), (3, 12), (3, 11), (3, 10), (4, 14), (4, 13), (4, 12), (4, 11), (4, 10), (4, 15), (4, 16)},
                    'last_season': {(90, 10), (90, 11), (90, 12), (90, 13), (90, 14), (90, 15), (90, 16), (90, 17), (90, 18)},
                    'goals_condition': {(1, 3), (1, 4), (1, 5), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (3, 3), (3, 4), (3, 5), (3, 6), (3, 7)},
                    'goals_latest': {(4, 0), (4, 1), (4, 2), (4, 3), (5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (6, 0), (6, 1), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (7, 5), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9)},
                    'last_season': {(90, 10), (90, 11), (90, 12), (90, 13), (90, 14), (90, 15), (90, 16), (90, 17), (90, 18)},
                    'goals_condition': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (3, 3), (3, 4), (3, 5), (3, 6), (3, 7)},
                    'goals_latest': {(7, 1), (7, 2), (7, 3), (8, 1), (8, 2), (8, 3), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15)},
                    'last_season': {(90, 3), (90, 4), (90, 5), (90, 6), (90, 7), (90, 8), (90, 9)},
                    'goals_condition': {(3, 6), (3, 7), (3, 8), (4, 6), (4, 7), (4, 8), (5, 6), (5, 7), (5, 8)},
                    'goals_latest': {(5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (7, 7), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(9, 11), (9, 12), (9, 13), (9, 14), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (10, 16), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 14), (12, 15), (12, 16), (12, 17)},
                    'last_season': {(90, 10), (90, 11), (90, 12), (90, 13), (90, 14), (90, 15), (90, 16), (90, 17), (90, 18)},
                    'goals_condition': {(2, 6), (2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(5, 4), (5, 5), (5, 6), (5, 7), (6, 4), (6, 5), (6, 6), (6, 7),(7, 4), (7, 5), (7, 6), (7, 7), (8, 4), (8, 5), (8, 6), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(9, 11), (9, 12), (9, 13), (9, 14), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (10, 16), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 14), (12, 15), (12, 16), (12, 17)},
                    'last_season': {(90, 10), (90, 11), (90, 12), (90, 13), (90, 14), (90, 15), (90, 16), (90, 17), (90, 18)},
                    'goals_condition': {(2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (3, 3), (3, 4), (3, 5), (3, 6)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (4, 0), (4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14)},
                    'last_season': {(3, 90), (4, 90), (5, 90), (6, 90), (7, 90)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7)},
                    'goals_latest': {(3, 1), (3, 2), (3, 3), (4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (9, 5)}
                },
                {
                    'current_rank': {(6, 5), (7, 5), (8, 5), (9, 5), (9, 6), (9, 7)},
                    'last_season': {(3, 90), (4, 90), (5, 90), (6, 90), (7, 90)},
                    'goals_condition': {(2, 4), (2, 5), (2, 6), (3, 3), (3, 4), (3, 5), (3, 6), (4, 4), (4, 5), (4, 6)},
                    'goals_latest': {(7, 3), (7, 4), (7, 5), (7, 6), (8, 3), (8, 4), (8, 5), (8, 6), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(1, 9), (1, 8), (1, 7), (1, 6), (1, 5), (1, 4), (1, 3), (2, 10), (2, 4), (2, 9), (2, 8), (2, 7), (2, 6), (2, 5), (3, 12), (3, 13), (3, 14), (3, 11), (3, 10), (3, 8), (3, 9), (3, 7), (3, 6), (4, 14), (4, 13), (4, 12), (4, 11), (4, 10), (4, 9), (4, 8), (4, 7), (4, 6)},
                    'last_season': {(3, 90), (4, 90), (5, 90), (6, 90), (7, 90)},
                    'goals_condition': {(1, 3), (1, 4), (1, 5)},
                    'goals_latest': {(3, 1), (3, 2), (3, 3), (4, 2), (4, 3), (5, 2), (5, 3), (5, 4), (6, 3), (6, 4), (6, 5)}
                },
                {
                    'current_rank': {(1, 9), (1, 8), (1, 7), (1, 6), (1, 5), (1, 4), (1, 3), (2, 10), (2, 4), (2, 9), (2, 8), (2, 7), (2, 6), (2, 5), (3, 12), (3, 13), (3, 14), (3, 11), (3, 10), (3, 8), (3, 9), (3, 7), (3, 6), (4, 14), (4, 13), (4, 12), (4, 11), (4, 10), (4, 9), (4, 8), (4, 7), (4, 6)},
                    'last_season': {(3, 90), (4, 90), (5, 90), (6, 90), (7, 90)},
                    'goals_condition': {(4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4)},
                    'goals_latest': {(7, 0), (7, 1), (7, 2), (8, 0), (8, 1), (8, 2), (9, 0), (9, 1), (9, 2)}
                },
                {
                    'current_rank': {(1, 9), (1, 8), (1, 7), (1, 6), (1, 5), (1, 4), (1, 3), (2, 10), (2, 4), (2, 9), (2, 8), (2, 7), (2, 6), (2, 5), (3, 12), (3, 13), (3, 14), (3, 11), (3, 10), (3, 8), (3, 9), (3, 7), (3, 6), (4, 14), (4, 13), (4, 12), (4, 11), (4, 10), (4, 9), (4, 8), (4, 7), (4, 6)},
                    'last_season': {(3, 90), (4, 90), (5, 90), (6, 90), (7, 90)},
                    'goals_condition': {(4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (5, 5), (5, 6), (5, 7), (5, 8), (5, 9)},
                    'goals_latest': {(6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(7, 6), (8, 6), (9, 6), (9, 7), (8, 7), (10, 6), (10, 7), (10, 8), (10, 9), (11, 6), (11, 7), (11, 8), (11, 9), (12, 8), (12, 9)},
                    'last_season': {(90, 3), (90, 4), (90, 5), (90, 6), (90, 7), (90, 8), (90, 9)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5)},
                    'goals_latest': {(2, 0), (2, 1), (2, 2), (2, 3), (3, 0), (3, 1), (3, 2), (3, 3), (4, 1), (4, 2), (4, 3), (5, 2), (5, 3), (5, 4)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 7), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15)},
                    'last_season': {(90, 3), (90, 4), (90, 5), (90, 6), (90, 7), (90, 8), (90, 9)},
                    'goals_condition': {(1, 2), (1, 3), (1, 4), (1, 5), (2, 2), (2, 3), (2, 4), (2, 5)},
                    'goals_latest': {(3, 0), (3, 1), (3, 2), (3, 3), (4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (6, 7), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15)},
                    'last_season': {(90, 3), (90, 4), (90, 5), (90, 6), (90, 7), (90, 8), (90, 9)},
                    'goals_condition': {(3, 3), (3, 4), (3, 5), (4, 3), (4, 4), (4, 5)},
                    'goals_latest': {(6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(1, 12), (1, 11), (1, 10), (1, 9), (1, 8), (1, 7), (1, 6), (1, 5), (1, 4), (2, 11), (2, 13), (2, 12), (2, 10), (2, 3), (2, 4), (2, 9), (2, 8), (2, 7), (2, 6), (2, 5), (3, 12), (3, 13), (3, 14), (3, 15), (3, 11), (3, 10), (3, 8), (3, 9), (3, 7), (3, 6), (4, 15), (4, 16), (4, 14), (4, 13), (4, 12), (4, 11), (4, 10), (4, 9), (4, 8), (4, 7), (4, 6)},
                    'last_season': {(90, 3), (90, 4), (90, 5), (90, 6), (90, 7), (90, 8), (90, 9)},
                    'goals_condition': {(0, 3), (0, 4), (0, 5), (1, 2), (1, 3), (1, 4), (1, 5), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 1), (3, 2), (3, 3)},
                    'goals_latest': {(5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(1, 12), (1, 11), (1, 10), (1, 9), (1, 8), (1, 7), (1, 6), (1, 5), (1, 4), (2, 11), (2, 13), (2, 12), (2, 10), (2, 3), (2, 4), (2, 9), (2, 8), (2, 7), (2, 6), (2, 5), (3, 12), (3, 13), (3, 14), (3, 15), (3, 11), (3, 10), (3, 8), (3, 9), (3, 7), (3, 6), (4, 15), (4, 16), (4, 14), (4, 13), (4, 12), (4, 11), (4, 10), (4, 9), (4, 8), (4, 7), (4, 6)},
                    'last_season': {(90, 3), (90, 4), (90, 5), (90, 6), (90, 7), (90, 8), (90, 9)},
                    'goals_condition': {(3, 4), (3, 5), (3, 6), (3, 7), (3, 8)},
                    'goals_latest': {(6, 1), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6)}
                },
                {
                    'current_rank': {(1, 6), (1, 5), (1, 4), (1, 3), (2, 3), (2, 4), (2, 6), (2, 5), (3, 4), (3, 5), (3, 6), (4, 5), (4, 7), (4, 6)},
                    'last_season': {(90, 3), (90, 4), (90, 5), (90, 6), (90, 7), (90, 8), (90, 9)},
                    'goals_condition': {(4, 1), (4, 2), (4, 3), (4, 4), (4, 5), (5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 3), (6, 4), (6, 5)},  
                    'goals_latest': {(9, 0), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (1, 14), (2, 10), (2, 11), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(2, 80), (3, 80), (4, 80)},
                    'goals_condition': {(3, 2), (3, 3), (3, 4)},
                    'goals_latest': {(6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4)}
                },
                {
                    'current_rank': {(1, 6), (1, 7), (1, 8), (1, 9), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (1, 14), (2, 10), (2, 11), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14)},
                    'last_season': {(2, 80), (3, 80), (4, 80)},
                    'goals_condition': {(3, 5), (3, 6), (3, 7), (3, 8), (3, 9)},
                    'goals_latest': {(5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 1), (9, 2), (9, 3), (9, 4)}
                }
            ]
            
            for match_data in matches_batch:
                try:
                    league_id = match_data.get('league_id')
                    season = match_data.get('season')
                    
                    if not season:
                        season = datetime.now().year
                    
                    try:
                        season = int(season)
                        last_season = season - 1
                    except:
                        continue

                    home_team_id = match_data.get('home_team_id')
                    away_team_id = match_data.get('away_team_id')
                    
                    home_current_data = self.fetch_team_standings_with_cache(home_team_id, league_id, season)
                    away_current_data = self.fetch_team_standings_with_cache(away_team_id, league_id, season)
                    
                    if not home_current_data or not away_current_data:
                        continue

                    home_current_rank = home_current_data.get('current_rank', 'N/A')
                    away_current_rank = away_current_data.get('current_rank', 'N/A')
                    
                    home_last_data = self._fetch_last_season_standings_with_cache(home_team_id, league_id, last_season)
                    away_last_data = self._fetch_last_season_standings_with_cache(away_team_id, league_id, last_season)
                    
                    home_last_rank = home_last_data.get('current_rank', 'N/A') if home_last_data else 'N/A'
                    away_last_rank = away_last_data.get('current_rank', 'N/A') if away_last_data else 'N/A'
                    

                    time_str = match_data.get('time', '')
                    match_date = ""
                    if time_str:
                        try:
                            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                            match_date = dt.strftime('%Y-%m-%d')
                        except:
                            match_date = datetime.now().strftime('%Y-%m-%d')
                    
                    home_goals_data = self.get_team_goals_from_cache(home_team_id, league_id, season, True, match_date)
                    home_goals_for = home_goals_data.get('goals_for', 0) if home_goals_data else 0
                    home_goals_against = home_goals_data.get('goals_against', 0) if home_goals_data else 0
                    
                    away_goals_data = self.get_team_goals_from_cache(away_team_id, league_id, season, False, match_date)
                    away_goals_for = away_goals_data.get('goals_for', 0) if away_goals_data else 0
                    away_goals_against = away_goals_data.get('goals_against', 0) if away_goals_data else 0
                    
                    def clean_rank(rank_str):
                        if rank_str in ('N/A', 'NEW'):
                            return 80
                        digits = ''.join(filter(str.isdigit, str(rank_str)))
                        return int(digits) if digits else 80
                    
                    ch = clean_rank(home_current_rank)
                    ca = clean_rank(away_current_rank)
                    lh = clean_rank(home_last_rank)
                    la = clean_rank(away_last_rank)
                    
                    current_pair = (ch, ca)
                    last_pair = (lh, la)
                    current_pair_rev = (ca, ch)
                    last_pair_rev = (la, lh)
                    
                    matched = False
                    for group in forbidden_groups:
                        # جميع الشروط الأربعة
                        normal_match = (current_pair in group['current_rank']) and (last_pair in group['last_season']) \
                                       and ((away_goals_for, away_goals_against) in group['goals_condition']) \
                                       and ((home_goals_for, home_goals_against) in group['goals_latest'])
                        
                        reversed_match = (current_pair_rev in group['current_rank']) and (last_pair_rev in group['last_season']) \
                                         and ((home_goals_for, home_goals_against) in group['goals_condition']) \
                                         and ((away_goals_for, away_goals_against) in group['goals_latest'])
                        
                        if normal_match or reversed_match:
                            matched = True
                            break
                    
                    if not matched:
                        self._auto_save_to_favorites_if_not_exists(match_data, "perfect_2_2", "Conditions not all met")
                        filtered_matches.append(match_data)
                        
                except Exception as e:
                    print(f"NS Perfect 2_2 Filter Error for match {match_data.get('id')}: {e}")
                    continue
            
            return filtered_matches
            
        except Exception as e:
            print(f"❌ ERROR in filter_ns_perfect_2_2_batch: {e}")
            return []

    def _get_team_goals_with_against(self, team_id, league_id, season, is_home_team, match_date=None):
        """جلب أهداف for و against معاً"""
        try:
            if not match_date:
                match_date = datetime.now().strftime('%Y-%m-%d')
            
            cached_data = self.get_team_goals_from_cache(team_id, league_id, season, is_home_team, match_date)
            
            if cached_data:
                goals_for = cached_data.get('goals_for', 0)
                goals_against = cached_data.get('goals_against', 0)
                return goals_for, goals_against
            
            print(f"🌐 جلب الأهداف للفلتر من API للفريق {team_id}")
            stats = self._fetch_team_last_3_matches(team_id, league_id, season, is_home_team)
            
            if stats:
                stats_dict = self._parse_stats_to_dict(stats)
                if stats_dict:
                    goals_for = stats_dict.get('goals_for', 0)
                    goals_against = stats_dict.get('goals_against', 0)
                    return goals_for, goals_against
            
            return None, None
                
        except Exception as e:
            print(f"Error in _get_team_goals_with_against for team {team_id}: {e}")
            return None, None

    def _auto_save_to_favorites_if_not_exists(self, match_data, filter_type, filter_result):
        """حفظ المباراة تلقائياً في المفضلة باستخدام set للتحقق السريع"""
        try:
            match_id = match_data.get('id')
            
            # ✅ تحديث: تحميل المفضلة أولاً للتأكد من البيانات الحالية
            self.load_favorites()
            
            # استخدام set للتحقق السريع
            favorite_ids = {f.get('id') for f in self.favorites}
            
            # التحقق إذا كانت المباراة موجودة بالفعل في المفضلة
            if match_id in favorite_ids:
                print(f"ℹ️ المباراة موجودة بالفعل في المفضلة: {match_id}")
                return False
            
            # إضافة معلومات الفلتر إلى بيانات المباراة
            enhanced_match_data = match_data.copy()
            enhanced_match_data['auto_saved_by_filter'] = filter_type
            enhanced_match_data['filter_result'] = filter_result
            enhanced_match_data['saved_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # إضافة المباراة إلى المفضلة
            self.favorites.append(enhanced_match_data)
            self.save_favorites()  # ✅ حفظ فوري في قاعدة البيانات
            
            # تحديث set للاستخدام المستقبلي
            favorite_ids.add(match_id)
            
            # عرض إشعار للمستخدم
            home_team = match_data.get('home_team', 'Unknown')
            away_team = match_data.get('away_team', 'Unknown')
            
            self.show_snackbar(
                f"⭐ تم حفظ المباراة تلقائياً بواسطة فلتر {filter_type}: {home_team} vs {away_team}",
                duration=4
            )
            
            print(f"✅ تم حفظ المباراة تلقائياً بواسطة فلتر {filter_type}: {match_id}")
            
            # ✅ تحديث الواجهة فوراً إذا كان في تبويب المفضلة
            if self.current_tab == 'favorites':
                Clock.schedule_once(lambda dt: self.show_favorites(), 0.1)
            
            return True
            
        except Exception as e:
            print(f"❌ خطأ في الحفظ التلقائي للمباراة: {e}")
            return False

    def _get_team_goals_for_filter_with_cache(self, team_id, league_id, season, is_home_team, match_date=None):
        """جلب الأهداف للفلتر مع استخدام الكاش المحسن"""
        try:
            if not match_date:
                match_date = datetime.now().strftime('%Y-%m-%d')
            
            cached_data = self.get_team_goals_from_cache(team_id, league_id, season, is_home_team, match_date)
            
            if cached_data:
                print(f"✅ استخدام الكاش للفلتر: {team_id}")
                goals_for = cached_data.get('goals_for', 0)
                matches_count = cached_data.get('matches_count', 0)
                return goals_for, matches_count
            
            print(f"🌐 جلب الأهداف للفلتر من API للفريق {team_id}")
            stats = self._fetch_team_last_3_matches(team_id, league_id, season, is_home_team)
            
            if stats:
                stats_dict = self._parse_stats_to_dict(stats)
                if stats_dict:
                    goals_for = stats_dict.get('goals_for', 0)
                    return goals_for, 3
            
            return None, 0
                
        except Exception as e:
            print(f"Error in _get_team_goals_for_filter_with_cache for team {team_id}: {e}")
            return None, 0

    # ⭐⭐ التحديث الرئيسي لحل مشكلة API المكررة
    def fetch_team_standings_with_cache(self, team_id, league_id, season):
        """جلب ترتيب الفريق مع استخدام الكاش - تم تحديثه لمنع الطلبات المكررة"""
        try:
            if not season:
                season = datetime.now().year
            
            # 1. تحقق من الكاش أولاً
            all_standings = self.storage.load_league_standings_from_cache(league_id, season)
            
            if all_standings:
                print(f"✅ استخدام الكاش الدائم لترتيب الدوري {league_id} للموسم {season}")
                for team_data in all_standings:
                    if team_data.get('team_id') == team_id:
                        return team_data
            
            # 2. إذا لم يكن هناك كاش، استخدم الدالة الجديدة لجلب جميع البيانات دفعة واحدة
            return self._fetch_and_cache_all_league_standings(league_id, season, team_id)
            
        except Exception as e:
            print(f"Error fetching team standings with cache: {e}")
            return {'current_rank': 'N/A', 'points': 0, 'form': ''}

    def _fetch_and_cache_all_league_standings(self, league_id, season, target_team_id=None):
        """جلب جميع فرق الدوري وحفظها في الكاش مرة واحدة فقط مع التحقق من التكرار"""
        try:
            # إنشاء مفتاح فريد لهذا الطلب لمنع التكرار
            api_lock_key = f"standings_{league_id}_{season}"
            
            # التحقق إذا كان نفس الطلب جارياً بالفعل
            if api_lock_key in self._standings_api_locks:
                print(f"⏳ يوجد طلب سابق للدوري {league_id} للموسم {season}")
                # انتظر قليلاً ثم تحقق من الكاش
                time.sleep(0.5)
                cached = self.storage.load_league_standings_from_cache(league_id, season)
                if cached:
                    for team_data in cached:
                        if team_data.get('team_id') == target_team_id:
                            return team_data
                return {'current_rank': 'N/A'}
            
            # وضع قفل لهذا الطلب
            self._standings_api_locks[api_lock_key] = True
            
            # التحقق أولاً من وجود البيانات في الكاش
            existing_cache = self.storage.load_league_standings_from_cache(league_id, season)
            if existing_cache and target_team_id:
                for team_data in existing_cache:
                    if team_data.get('team_id') == target_team_id:
                        print(f"✅ استخدام البيانات الموجودة في الكاش للدوري {league_id}")
                        # إزالة القفل
                        del self._standings_api_locks[api_lock_key]
                        return team_data
            
            print(f"🌐 جلب جميع فرق الدوري {league_id} للموسم {season}")
            
            url = f"{self.base_url}/standings"
            params = {
                'league': league_id,
                'season': season
            }
            
            print(f"📡 API Request: {url}?league={league_id}&season={season}")
            
            response = self.fetch_with_retry(url, params)
            
            target_team_data = None
            
            if response and response.status_code == 200:
                data = response.json()
                standings = data.get('response', [])
                
                if standings:
                    league_data = standings[0].get('league', {})
                    league_standings = league_data.get('standings', [])
                    
                    all_teams_data = []
                    
                    for standing_group in league_standings:
                        for team_standing in standing_group:
                            current_team_id = team_standing.get('team', {}).get('id')
                            team_info = {
                                'team_id': current_team_id,
                                'team_name': team_standing.get('team', {}).get('name'),
                                'current_rank': str(team_standing.get('rank')),
                                'season': season,
                                'league_id': league_id,
                                'league_name': league_data.get('name', '')
                            }
                            all_teams_data.append(team_info)
                            
                            # إذا كان هذا هو الفريق المطلوب
                            if target_team_id and current_team_id == target_team_id:
                                target_team_data = team_info
                    
                    # حفظ جميع الفرق في الكاش مرة واحدة فقط
                    if all_teams_data:
                        self.storage.save_league_standings_to_cache(league_id, season, all_teams_data)
                        print(f"✅ تم حفظ {len(all_teams_data)} فريق في كاش الترتيب للدوري {league_id}")
            
            # إزالة القفل
            del self._standings_api_locks[api_lock_key]
            
            return target_team_data if target_team_data else {'current_rank': 'N/A'}
            
        except Exception as e:
            print(f"Error fetching all league standings: {e}")
            # إزالة القلع في حالة الخطأ
            api_lock_key = f"standings_{league_id}_{season}"
            if api_lock_key in self._standings_api_locks:
                del self._standings_api_locks[api_lock_key]
            return {'current_rank': 'N/A'}

    # ⭐⭐ تحديث الدوال الأخرى التي قد تسبب طلبات مكررة
    def _fetch_last_season_standings_with_cache(self, team_id, league_id, season):
        """جلب ترتيب الموسم الماضي من الكاش مع منع الطلبات المكررة"""
        try:
            # 1. إذا كان الموسم الحالي، ابحث في جدول الموسم الحالي
            if not season:
                season = datetime.now().year
                cached_league_data = self.storage.load_league_standings_from_cache(league_id, season)
            else:  # الموسم الماضي
                # 2. ابحث أولاً في نفس الدوري للموسم الماضي
                cached_league_data = self.storage.load_last_season_standings_from_cache(league_id, season)
                
            if cached_league_data:
                # البحث عن الفريق المطلوب في بيانات الدوري المخزنة
                for team_data in cached_league_data:
                    if team_data.get('team_id') == team_id:
                        return team_data
            
            # 3. إذا لم يتم العثور على الفريق في نفس الدوري، ابحث في جميع كاش الموسم الماضي حسب team_id
            print(f"🔍 البحث عن الفريق {team_id} في دوريات أخرى للموسم {season}")
            
            # محاولة البحث في قاعدة بيانات كاش الموسم الماضي حسب team_id
            last_season_data = self._find_team_in_last_season_cache_by_id(team_id, season)
            if last_season_data:
                print(f"✅ تم العثور على الفريق {team_id} في دوري آخر: {last_season_data.get('league_name')}")
                return last_season_data
            
            # 4. إذا لم يكن الدوري في الكاش، جلب الدوري بالكامل من API مرة واحدة فقط
            print(f"🌐 جلب جميع فرق الدوري {league_id} للموسم {season}")
            
            # استخدام نفس مبدأ منع التكرار
            api_lock_key = f"last_season_{league_id}_{season}"
            if api_lock_key in self._standings_api_locks:
                print(f"⏳ يوجد طلب سابق للموسم الماضي للدوري {league_id}")
                time.sleep(0.5)
                cached = self.storage.load_last_season_standings_from_cache(league_id, season)
                if cached:
                    for team_data in cached:
                        if team_data.get('team_id') == team_id:
                            return team_data
                return None
            
            self._standings_api_locks[api_lock_key] = True
            
            all_league_teams = self._fetch_all_league_teams_last_season(league_id, season)
            
            if all_league_teams:
                self.storage.save_last_season_standings_to_cache(league_id, season, all_league_teams)
                
                for team_data in all_league_teams:
                    if team_data.get('team_id') == team_id:
                        # إزالة القفل بعد الانتهاء
                        del self._standings_api_locks[api_lock_key]
                        return team_data
            
            # إزالة القفل
            if api_lock_key in self._standings_api_locks:
                del self._standings_api_locks[api_lock_key]
            
            return None
            
        except Exception as e:
            print(f"Error fetching last season standings with cache: {e}")
            # تنظيف القفل في حالة الخطأ
            api_lock_key = f"last_season_{league_id}_{season}"
            if api_lock_key in self._standings_api_locks:
                del self._standings_api_locks[api_lock_key]
            return None

    def _find_team_in_last_season_cache_by_id(self, team_id, season):
        """البحث عن الفريق في كاش الموسم الماضي حسب team_id"""
        try:
            team_data = self.storage.get_last_season_cache_by_team(team_id, season)
            if team_data:
                print(f"✅ وجد الفريق {team_id} في كاش الموسم الماضي")
                team_data['from_different_league'] = True
                return team_data
            
            return None
        except Exception as e:
            print(f"Error finding team in last season cache: {e}")
            return None

    def _fetch_all_league_teams_last_season(self, league_id, last_season):
        """جلب جميع فرق الدوري للموسم الماضي"""
        try:
            if not last_season:
                last_season = datetime.now().year - 1
                
            print(f"🔄 جلب جميع فرق الدوري {league_id} للموسم {last_season}")
            
            url = f"{self.base_url}/standings"
            params = {
                'league': league_id,
                'season': last_season
            }
            
            response = self.fetch_with_retry(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                
                if data.get('response'):
                    standings_data = data['response'][0]
                    league_standings = standings_data.get('league', {}).get('standings', [])
                    
                    all_teams_data = []
                    
                    if league_standings and len(league_standings) > 0:
                        for standing_group in league_standings:
                            for team_standing in standing_group:
                                team_data = {
                                    'team_id': team_standing.get('team', {}).get('id'),
                                    'team_name': team_standing.get('team', {}).get('name'),
                                    'current_rank': str(team_standing.get('rank', 'N/A')),
                                    'season': last_season,
                                    'league_id': league_id,
                                    'league_name': standings_data.get('league', {}).get('name', '')
                                }
                                all_teams_data.append(team_data)
                        
                        print(f"✅ تم جلب {len(all_teams_data)} فريق من الدوري {league_id} للموسم الماضي {last_season}")
                        return all_teams_data
            
            return None
            
        except Exception as e:
            print(f"Error fetching all league teams: {e}")
            return None

    def is_hidden(self, match_id):
        # استخدام set للتحقق السريع بدلاً من list
        hidden_ids = {m.get('id') for m in self.hidden_matches}
        return match_id in hidden_ids

    def is_favorite(self, match_id):
        # استخدام set للتحقق السريع بدلاً من list
        favorite_ids = {f.get('id') for f in self.favorites}
        return match_id in favorite_ids

    def load_favorites(self):
        self.favorites = self.storage.load_favorites()

    def save_favorites(self):
        self.storage.save_favorites(self.favorites)

    def load_hidden_matches(self):
        self.hidden_matches = self.storage.load_hidden_matches()

    def save_hidden_matches(self):
        self.storage.save_hidden_matches(self.hidden_matches)

    def load_league_selection(self):
        self.selected_leagues = self.storage.load_league_selection()

    def save_league_selection(self):
        self.storage.save_league_selection(self.selected_leagues)

    def load_favorite_leagues(self):
        self.favorite_leagues = self.storage.load_favorite_leagues()

    def save_favorite_leagues(self):
        self.storage.save_favorite_leagues(self.favorite_leagues)

    def toggle_filter_ns_perfect_1_1(self):
        self.filter_ns_perfect_1_1_enabled = not self.filter_ns_perfect_1_1_enabled
        self.save_filter_state()
        status = "Enabled" if self.filter_ns_perfect_1_1_enabled else "Disabled"
        self.show_snackbar(f"NS Filter (Perfect 1_1) is now {status}")
        self.show_profile()

    def toggle_filter_ns_perfect_2_2(self):
        self.filter_ns_perfect_2_2_enabled = not self.filter_ns_perfect_2_2_enabled
        self.save_filter_state()
        status = "Enabled" if self.filter_ns_perfect_2_2_enabled else "Disabled"
        self.show_snackbar(f"NS Filter (Perfect 2_2) is now {status}")
        self.show_profile()

    def on_calendar_date_selected(self, selected_date):
        self.current_calendar_date = selected_date
        self.calendar_mode = True
        
        today = datetime.now().date()
        if selected_date == today:
            self.current_title = "Today's Matches"
        elif selected_date == today + timedelta(days=1):
            self.current_title = "Tomorrow's Matches"
        elif selected_date == today + timedelta(days=2):
            self.current_title = "Day After Tomorrow's Matches"
        else:
            self.current_title = f"Matches for {selected_date.strftime('%d/%m/%Y')}"
        
        print(f"🗓️ تم اختيار التاريخ: {selected_date}")
        self.show_calendar_matches(selected_date)

    def show_calendar_matches(self, target_date):
        self.show_loading(f"Loading scheduled matches for {target_date.strftime('%d/%m/%Y')}...")
        
        future = self.executor.submit(self._fetch_and_display_calendar_matches, target_date)
        self.futures.append(future)
        
    def _fetch_and_display_calendar_matches(self, target_date):
        try:
            matches = self.fetch_matches_by_date_improved(target_date)
            processed_matches = self.process_matches_improved(matches)
            
            Clock.schedule_once(lambda dt: self.display_calendar_matches_improved(processed_matches, target_date), 0)
        except Exception as e:
            print(f"❌ خطأ في جلب المباريات: {e}")
            Clock.schedule_once(lambda dt: self.display_calendar_matches_improved([], target_date), 0)

    def process_api_response_improved(self, api_matches):
        processed_matches = []
        
        for match in api_matches:
            try:
                fixture = match.get('fixture', {})
                teams = match.get('teams', {})
                goals = match.get('goals', {})
                league = match.get('league', {})
                
                home_team = teams.get('home', {})
                away_team = teams.get('away', {})
                
                home_team_name = home_team.get('name', 'Home Team')
                away_team_name = away_team.get('name', 'Away Team')
                
                full_home_team_name = home_team.get('name', 'Home Team')
                full_away_team_name = away_team.get('name', 'Away Team')
                
                home_score = goals.get('home')
                away_score = goals.get('away')
                
                status = fixture.get('status', {}).get('short', 'NS')
                elapsed = fixture.get('status', {}).get('elapsed')
                
                processed_match = {
                    'id': fixture.get('id'),
                    'league': league.get('name', 'Unknown League'),
                    'league_id': league.get('id'),
                    'season': league.get('season'),
                    
                    'home_team': home_team_name,
                    'full_home_team': full_home_team_name,
                    'home_team_id': home_team.get('id'),
                    'away_team': away_team_name,
                    'full_away_team': full_away_team_name,
                    'away_team_id': away_team.get('id'),
                    'home_score': home_score,
                    'away_score': away_score,
                    'status': status,
                    'elapsed': elapsed,
                    'time': fixture.get('date', ''),
                }
                
                processed_matches.append(processed_match)
                
            except Exception as e:
                print(f"Error processing match: {e}")
                continue
                
        return processed_matches

    def process_matches_improved(self, matches):
        processed = []
        for match in matches:
            try:
                match.setdefault('home_score', None)
                match.setdefault('away_score', None)
                match.setdefault('elapsed', None)
                match.setdefault('events', [])
                
                time_str = match.get('time', '')
                if time_str:
                    try:
                        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        match['formatted_time'] = dt.strftime('%H:%M')
                    except:
                        match['formatted_time'] = time_str[:16] if time_str else "TBD"
                else:
                    match['formatted_time'] = 'TBD'
                
                processed.append(match)
            except Exception as e:
                print(f"Error in match processing: {e}")
                continue
        return processed

    def group_matches_by_league(self, matches):
        """تجميع المباريات حسب الدوري"""
        leagues_dict = {}
        
        for match in matches:
            league_id = match.get('league_id')
            league_name = match.get('league', 'Unknown League')
            
            if league_id not in leagues_dict:
                leagues_dict[league_id] = {
                    'name': league_name,
                    'id': league_id,
                    'matches': []
                }
            
            leagues_dict[league_id]['matches'].append(match)
        
        sorted_leagues = sorted(leagues_dict.values(), key=lambda x: x['name'])
        return sorted_leagues

    def display_leagues_batch(self, leagues_list, container, is_append=True):
        """عرض دفعة من الدوريات"""
        start_index = self.current_leagues_batch * self.leagues_per_batch
        end_index = start_index + self.leagues_per_batch
        
        current_batch = leagues_list[start_index:end_index]
        
        if not is_append:
            headers = []
            for widget in container.children[:]:
                if isinstance(widget, OneLineListItem) and ("📅" in widget.text or "🏆" in widget.text):
                    headers.append(widget)
            
            container.clear_widgets()

        for league_data in current_batch:
            league_header = OneLineListItem(
                text=f"🏆 {league_data['name']} ({len(league_data['matches'])} matches)"
            )
            league_header.md_bg_color = get_color_from_hex("#E8F5E8")
            league_header.size_hint_y = None
            league_header.height = dp(40)
            container.add_widget(league_header)
            
            for match in league_data['matches']:
                item = OptimizedCompactMatchItem(match_data=match)
                container.add_widget(item)
        
        self.current_leagues_batch += 1

    @mainthread
    def display_calendar_matches_improved(self, matches, target_date):
        """عرض المباريات المجدولة مع تطبيق الفلترات بالدفعات"""
        container = self.root.ids.main_list
        container.clear_widgets()
        
        today = datetime.now().date()
        
        if target_date == today:
            date_label = "📅 TODAY'S SCHEDULED MATCHES"
        elif target_date == today + timedelta(days=1):
            date_label = "📅 TOMORROW'S SCHEDULED MATCHES"
        elif target_date == today + timedelta(days=2):
            date_label = "📅 DAY AFTER TOMORROW'S SCHEDULED MATCHES"
        else:
            date_display = target_date.strftime('%d/%m/%Y')
            date_label = f"📅 SCHEDULED MATCHES ({date_display})"

        header = OneLineListItem(text=date_label)
        header.md_bg_color = get_color_from_hex("#E3F2FD")
        container.add_widget(header)
        
        if matches:
            # استخدام set لإزالة التكرارات فوراً
            seen_ids = set()
            unique_matches = []
            
            for match in matches:
                match_id = match.get('id')
                if match_id and match_id not in seen_ids:
                    seen_ids.add(match_id)
                    unique_matches.append(match)
            
            print(f"✅ إزالة التكرارات: {len(matches)} -> {len(unique_matches)} مباراة")
            
            required_league_ids = self.get_required_league_ids()
            
            if required_league_ids:
                # استخدام set للفلترة السريعة
                required_ids_set = set(required_league_ids)
                filtered_matches = [
                    match for match in unique_matches
                    if match.get('league_id') in required_ids_set
                ]
                print(f"🔍 بعد التصفية حسب الدوري: {len(filtered_matches)} مباراة مجدولة")
            else:
                filtered_matches = unique_matches

            # تطبيق الفلترات بالدفعات
            batch_size = 600
            total_matches = len(filtered_matches)
            
            if self.filter_ns_perfect_1_1_enabled:
                print(f"🎯 تطبيق فلتر NS Perfect 1_1 على {len(filtered_matches)} مباراة بالدفعات (كل دفعة {batch_size})")
                
                filtered_by_1_1 = []
                for i in range(0, total_matches, batch_size):
                    batch = filtered_matches[i:i + batch_size]
                    print(f"🔍 معالجة دفعة {i//batch_size + 1}: {len(batch)} مباراة")
                    
                    batch_filtered = self.filter_ns_perfect_1_1_batch(batch)
                    filtered_by_1_1.extend(batch_filtered)
                    
                    # تحديث الواجهة بين الدفعات
                    Clock.schedule_once(lambda dt, progress=((i + len(batch)) / total_matches * 100): 
                        self.show_loading(f"Filtering NS Perfect 1_1... {int(progress)}%", progress), 0)
                
                filtered_matches = filtered_by_1_1
                print(f"🎯 بعد تطبيق فلتر NS Perfect 1_1: {len(filtered_matches)} مباراة")
            
            if self.filter_ns_perfect_2_2_enabled:
                print(f"🎯 تطبيق فلتر NS Perfect 2_2 على {len(filtered_matches)} مباراة بالدفعات (كل دفعة {batch_size})")
                
                filtered_by_2_2 = []
                for i in range(0, len(filtered_matches), batch_size):
                    batch = filtered_matches[i:i + batch_size]
                    print(f"🔍 معالجة دفعة {i//batch_size + 1}: {len(batch)} مباراة")
                    
                    batch_filtered = self.filter_ns_perfect_2_2_batch(batch)
                    filtered_by_2_2.extend(batch_filtered)
                    
                    # تحديث الواجهة بين الدفعات
                    Clock.schedule_once(lambda dt, progress=((i + len(batch)) / total_matches * 100): 
                        self.show_loading(f"Filtering NS Perfect 2_2... {int(progress)}%", progress), 0)
                
                filtered_matches = filtered_by_2_2
                print(f"🎯 بعد تطبيق فلتر NS Perfect 2_2: {len(filtered_matches)} مباراة")
            
            final_matches = self.filter_out_hidden_and_favorite_matches(filtered_matches)
            print(f"🚫 النتيجة النهائية: {len(final_matches)} مباراة مجدولة")
            
            if final_matches:
                filter_info = []
                if self.filter_ns_perfect_1_1_enabled:
                    filter_info.append("NS Perfect 1_1 (Batch)")
                if self.filter_ns_perfect_2_2_enabled:
                    filter_info.append("NS Perfect 2_2 (Batch)")
                
                if filter_info:
                    filter_label = MDLabel(
                        text=f"Active filters: {' + '.join(filter_info)}",
                        font_style='Caption',
                        halign='center',
                        theme_text_color='Secondary',
                        size_hint_y=None,
                        height=dp(20)
                    )
                    container.add_widget(filter_label)
                
                count_label = MDLabel(
                    text=f"Found {len(final_matches)} scheduled matches",
                    font_style='Caption',
                    halign='center',
                    theme_text_color='Secondary',
                    size_hint_y=None,
                    height=dp(25)
                )
                container.add_widget(count_label)
                
                matches_by_league = self.group_matches_by_league(final_matches)
                
                self.grouped_leagues_cache = {str(i): league for i, league in enumerate(matches_by_league)}
                
                self.all_leagues_count = len(matches_by_league)
                self.current_leagues_batch = 0
                
                self.display_leagues_batch(matches_by_league, container, is_append=True)
                
                self.show_load_more_button(container, matches_by_league)
                
            else:
                no_matches_text = "terminé"
                if required_league_ids:
                    no_matches_text += " with current league"
                filter_texts = []
                if self.filter_ns_perfect_1_1_enabled:
                    filter_texts.append("NS Perfect 1_1 (Batch)")
                if self.filter_ns_perfect_2_2_enabled:
                    filter_texts.append("NS Perfect 2_2 (Batch)")
                if filter_texts:
                    no_matches_text += f": {' + '.join(filter_texts)}"
                self.show_empty_message(no_matches_text)
        else:
            self.show_empty_message(f"matches found for {target_date.strftime('%d/%m/%Y')}")

    def show_load_more_button(self, container, leagues_list):
        """عرض زر تحميل المزيد"""
        total_leagues = len(leagues_list)
        displayed_leagues = self.current_leagues_batch * self.leagues_per_batch
        
        if displayed_leagues < total_leagues:
            remaining_leagues = total_leagues - displayed_leagues
            leagues_in_next_batch = min(remaining_leagues, self.leagues_per_batch)
            
            load_more_button = MDRaisedButton(
                text=f"⬇️ Load more leagues ({leagues_in_next_batch} leagues remaining)",
                size_hint=(None, None),
                size=(dp(300), dp(40)),
                pos_hint={'center_x': 0.5},
                md_bg_color=get_color_from_hex("#2196F3"),
                on_release=lambda x: self.load_more_leagues(leagues_list, container)
            )
            
            container.add_widget(load_more_button)
            self.show_load_more = True
        else:
            self.show_load_more = False

    def load_more_leagues(self, leagues_list, container):
        """تحميل دفعة إضافية من الدوريات"""
        for widget in container.children[:]:
            if isinstance(widget, MDRaisedButton) and "Load more leagues" in widget.text:
                container.remove_widget(widget)
                break
        
        self.display_leagues_batch(leagues_list, container, is_append=False)
        
        self.show_load_more_button(container, leagues_list)
        
        Clock.schedule_once(lambda dt: self.scroll_to_top(), 0.1)

    def scroll_to_top(self):
        """التمرير إلى أعلى القائمة"""
        try:
            scroll_view = self.root.ids.main_scroll
            scroll_view.scroll_y = 1
        except Exception as e:
            print(f"❌ خطأ في التمرير: {e}")

    def scroll_to_bottom(self):
        """التمرير إلى أسفل القائمة"""
        try:
            scroll_view = self.root.ids.main_scroll
            scroll_view.scroll_y = 0
        except Exception as e:
            print(f"❌ خطأ في التمرير: {e}")

    # ⭐⭐ تحديث دالة البوب أب الرئيسية
    def show_stats_popup_improved(self, match_data):
        try:
            required_fields = ['home_team_id', 'away_team_id', 'league_id']
            if not all(match_data.get(field) for field in required_fields):
                self.show_snackbar("⚠️ بيانات المباراة غير مكتملة")
                return
                
            popup = StatsPopup()
            popup.home_team_name = match_data.get('full_home_team', match_data.get('home_team', ''))
            popup.away_team_name = match_data.get('full_away_team', match_data.get('away_team', ''))
            
            popup.first_team_goals_for = "?"
            popup.first_team_goals_against = "?"
            popup.second_team_goals_for = "?"
            popup.second_team_goals_against = "?"
            
            from kivy.core.window import Window
            Window.add_widget(popup)
            
            Clock.schedule_once(lambda dt: self.load_popup_statistics_with_scheduled_cache(match_data, popup), 0.1)
            
            anim = Animation(opacity=1, duration=0.3)
            anim.start(popup)
            
            Clock.schedule_once(lambda dt: self.close_stats_popup(popup), 30)
        
        except Exception as e:
            print(f"❌ Error showing stats popup: {e}")
            self.show_snackbar("⚠️ خطأ في فتح الإحصائيات")

    def load_popup_statistics_with_scheduled_cache(self, match_data, popup):
        """جلب الإحصائيات مع استخدام كاش الفرق المجدولة فقط"""
        try:
            home_team_id = match_data.get('home_team_id')
            away_team_id = match_data.get('away_team_id')
            league_id = match_data.get('league_id')
            season = match_data.get('season')
            
            if not season:
                season = datetime.now().year
            
            # استخراج تاريخ المباراة
            time_str = match_data.get('time', '')
            match_date = ""
            if time_str:
                try:
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    match_date = dt.strftime('%Y-%m-%d')
                except:
                    match_date = datetime.now().strftime('%Y-%m-%d')
            
            if not match_date:
                match_date = datetime.now().strftime('%Y-%m-%d')
            
            if home_team_id and away_team_id and league_id:
                future = self.executor.submit(
                    self._fetch_popup_stats_with_scheduled_cache, 
                    match_data, popup, home_team_id, away_team_id, league_id, season, match_date
                )
                self.futures.append(future)
                
        except Exception as e:
            print(f"❌ خطأ في تحميل الإحصائيات: {e}")

    def _fetch_popup_stats_with_scheduled_cache(self, match_data, popup, home_team_id, away_team_id, league_id, season, match_date):
        """دالة مساعدة - تجلب فقط فرق المباريات المجدولة"""
        try:
            cache_key = f"{league_id}_{season}_{match_date}"
            
            if cache_key not in self.scheduled_teams_goals_cache:
                print(f"🔄 جلب إحصائيات فرق المباريات المجدولة للدوري {league_id}")
                
                if cache_key in self.scheduled_teams_loading and self.scheduled_teams_loading[cache_key]:
                    print(f"⚠️ كاش الدوري {league_id} قيد التحميل بالفعل")
                else:
                    self.scheduled_teams_loading[cache_key] = True
                    
                    scheduled_teams_data = self.fetch_scheduled_teams_goals(league_id, season, match_date)
                    
                    if scheduled_teams_data:
                        self.scheduled_teams_goals_cache[cache_key] = scheduled_teams_data
                        print(f"✅ تم تحميل {len(scheduled_teams_data)} حالة لفرق المباريات المجدولة")
                    
                    self.scheduled_teams_loading[cache_key] = False
            
            league_data = self.scheduled_teams_goals_cache.get(cache_key, {})
            
            first_team_role, second_team_role = self.determine_team_order(match_data)
            
            if first_team_role == 'home':
                home_key = f"{home_team_id}_home"
                away_key = f"{away_team_id}_away"
                
                first_stats_dict = league_data.get(home_key)
                second_stats_dict = league_data.get(away_key)
                
                first_stats = self._dict_to_stats_str(first_stats_dict) if first_stats_dict else None
                second_stats = self._dict_to_stats_str(second_stats_dict) if second_stats_dict else None
                
                first_name_display = popup.home_team_name 
                second_name_display = popup.away_team_name
                
                first_standings = self.fetch_team_standings_improved(home_team_id, league_id, season)
                second_standings = self.fetch_team_standings_improved(away_team_id, league_id, season)
            else:
                away_key = f"{away_team_id}_away"
                home_key = f"{home_team_id}_home"
                
                first_stats_dict = league_data.get(away_key)
                second_stats_dict = league_data.get(home_key)
                
                first_stats = self._dict_to_stats_str(first_stats_dict) if first_stats_dict else None
                second_stats = self._dict_to_stats_str(second_stats_dict) if second_stats_dict else None
                
                first_name_display = popup.away_team_name
                second_name_display = popup.home_team_name
                
                first_standings = self.fetch_team_standings_improved(away_team_id, league_id, season)
                second_standings = self.fetch_team_standings_improved(home_team_id, league_id, season)
            
            Clock.schedule_once(lambda dt: self.update_popup_stats(
                popup, first_stats, second_stats, 
                first_name_display, second_name_display,
                first_standings, second_standings
            ), 0)
            
        except Exception as e:
            print(f"❌ خطأ في جلب الإحصائيات: {e}")
            Clock.schedule_once(lambda dt: self.update_popup_stats(
                popup, None, None,
                popup.home_team_name, popup.away_team_name,
                None, None
            ), 0)

    def _dict_to_stats_str(self, stats_dict):
        """تحويل القاموس إلى نص إحصائيات"""
        if not stats_dict:
            return None
        
        return f"{stats_dict['color_type']}:{stats_dict['goals_for']}:{stats_dict['goals_against']}"

    def fetch_team_standings_improved(self, team_id, league_id, season):
        """جلب ترتيب الفريق مع الكاش - تم تحديثه"""
        try:
            if not season:
                season = datetime.now().year
            
            current_data = self.fetch_team_standings_with_cache(team_id, league_id, season)
            
            if current_data:
                current_rank = str(current_data.get('current_rank', 'N/A'))
            else:
                current_rank = 'N/A'
            
            last_season = season - 1
            last_season_data = self._fetch_last_season_standings_with_cache(team_id, league_id, last_season)
            
            last_rank_display, last_rank_type = self._determine_last_rank_display(last_season_data, current_data)
            
            combined_standings = {
                'current_rank': current_rank,
                'last_rank': last_rank_display,
                'last_rank_type': last_rank_type,
                'played': current_data.get('played', 'N/A') if current_data else 'N/A',
                'current_season': season,
                'last_season': last_season
            }
            
            print(f"📊 مصدر الترتيب الحالي: league_standings_cache للموسم {season}")
            print(f"📊 مصدر الترتيب الماضي: last_season_standings_cache للموسم {last_season}")
            print(f"✅ جلب الترتيب: الحالي={current_rank}, الماضي={last_rank_display}")
            return combined_standings
                
        except Exception as e:
            print(f"Error fetching team standings: {e}")
            return {
                'current_rank': 'N/A',
                'last_rank': 'N/A',
                'last_rank_type': 'normal',
                'played': 'N/A',
                'current_season': season,
                'last_season': season - 1
            }

    def _determine_last_rank_display(self, last_standings, current_standings):
        """تحديد كيفية عرض ترتيب الموسم الماضي"""
        if not last_standings:
            return "N/A", "normal"
        
        last_rank = str(last_standings.get('current_rank', 'N/A'))
        
        if last_rank == "N/A":
            return "NEW", "new_team"
        
        last_league_id = last_standings.get('league_id', None)
        
        if last_standings.get('from_different_league', False):
            return f"{last_rank}", "different_league_blue"
        
        if not current_standings:
            return last_rank, "normal"
        
        current_league_id = current_standings.get('league_id', None)
        
        if last_league_id is not None and last_league_id != current_league_id:
            return f"{last_rank}", "moved_league"
        
        return last_rank, "normal"

    def determine_team_order(self, match_data):
        home_score = match_data.get('home_score')
        away_score = match_data.get('away_score')
        status = match_data.get('status', 'NS')
        
        home_score = home_score if home_score is not None else 0
        away_score = away_score if away_score is not None else 0
        
        if (home_score == 0 and away_score == 0) or status == 'NS':
            home_team_id = match_data.get('home_team_id')
            away_team_id = match_data.get('away_team_id')
            league_id = match_data.get('league_id')
            season = match_data.get('season')
            
            if not season:
                season = datetime.now().year
                
            if home_team_id and away_team_id and league_id:
                # استخراج تاريخ المباراة للكاش
                time_str = match_data.get('time', '')
                match_date = ""
                if time_str:
                    try:
                        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        match_date = dt.strftime('%Y-%m-%d')
                    except:
                        match_date = datetime.now().strftime('%Y-%m-%d')
                
                home_stats_dict = self.get_team_goals_from_cache(home_team_id, league_id, season, True, match_date)
                away_stats_dict = self.get_team_goals_from_cache(away_team_id, league_id, season, False, match_date)
                
                home_goals_for = home_stats_dict.get('goals_for', 0) if home_stats_dict else 0
                away_goals_for = away_stats_dict.get('goals_for', 0) if away_stats_dict else 0
                
                if home_goals_for >= away_goals_for:
                    return 'home', 'away'
                else:
                    return 'away', 'home'
        
        if home_score < away_score:
            return 'home', 'away'
        elif away_score < home_score:
            return 'away', 'home'
        else:
            return 'home', 'away'

    def add_hidden_match(self, match):
        if not self.is_hidden(match.get('id')):
            self.hidden_matches.append(match.copy())
            self.save_hidden_matches()
            print(f"✅ تم إضافة المباراة المخفية: {match.get('home_team')} vs {match.get('away_team')}")

    def remove_hidden_match(self, match_id):
        self.hidden_matches = [m for m in self.hidden_matches if m.get('id') != match_id]
        self.save_hidden_matches()
        print(f"🗑️ تم حذف المباراة المخفية {match_id} من قاعدة البيانات")

    def remove_match_from_all_lists(self, match_id):
        self.matches = [m for m in self.matches if m.get('id') != match_id]        
        self.today_matches = [m for m in self.today_matches if m.get('id') != match_id]         
        self.filtered_matches = [m for m in self.filtered_matches if m.get('id') != match_id]
        
        print(f"🗑️ تمت إزالة المباراة {match_id} من جميع القوائم الداخلية")

    def add_favorite(self, match):
        if not self.is_favorite(match.get('id')):
            self.favorites.append(match.copy())
            self.save_favorites()
            if self.current_tab == 'live' and not self.calendar_mode:
                self.show_live_matches()

    def remove_favorite(self, match_id):
        self.favorites = [f for f in self.favorites if f.get('id') != match_id]
        self.save_favorites()
        if self.current_tab == 'live' and not self.calendar_mode:
            self.show_live_matches()
        elif self.current_tab == 'favorites':
            self.show_favorites()

    def is_favorite_league(self, league_id):
        return any(f.get('id') == league_id for f in self.favorite_leagues)

    def add_favorite_league(self, league_name, league_id):
        if not self.is_favorite_league(league_id):
            self.favorite_leagues.append({'name': league_name, 'id': league_id})
            self.save_favorite_leagues()
            self.show_snackbar(f"League added to favorites: {league_name}")

    def remove_favorite_league(self, league_id):
        self.favorite_leagues = [f for f in self.favorite_leagues if f.get('id') != league_id]
        self.save_favorite_leagues()
        self.show_snackbar("League removed from favorites")
        if self.current_tab == 'favorites':
            self.show_favorites()

    def is_league_selected(self, league_id):
        return any(l.get('id') == league_id for l in self.selected_leagues)

    def fetch_leagues(self):
        try:
            url = f"{self.base_url}/leagues"
            params = {'current': 'true'}
            
            response = self.fetch_with_retry(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                if data.get('response'):
                    leagues = []
                    for league in data['response']:
                        league_info = league.get('league', {})
                        country_info = league.get('country', {})
                        
                        league_data = {
                            'id': league_info.get('id'),
                            'name': league_info.get('name'),
                            'type': league_info.get('type'),
                            'logo': league_info.get('logo'),
                            'country_name': country_info.get('name'),
                            'country_code': country_info.get('code'),
                            'flag': country_info.get('flag'),
                            'season': league.get('seasons', [{}])[0].get('year') if league.get('seasons') else None
                        }
                        leagues.append(league_data)
                    
                    return leagues
            return []
        except Exception as e:
            print(f"Error fetching leagues: {e}")
            return []

    def fetch_live_matches_sync(self):
        try:
            url = f"{self.base_url}/fixtures"
            params = {'live': 'all'}
            
            response = self.fetch_with_retry(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                if data.get('response'):
                    matches = self.process_api_response_improved(data['response'])
                    live_matches = [match for match in matches if match.get('status') in ['1H', '2H', 'HT', 'ET', 'P', 'BT', 'LIVE']]

                    live_matches = self.filter_out_hidden_matches_immediately(live_matches)
                    
                    return live_matches
                else:
                    return []
            else:
                return []
                
        except Exception as e:
            print(f"Error fetching live matches: {e}")
            return []

    def fetch_with_retry(self, url, params, max_retries=2):
        """طلب API مع تسجيل تفصيلي لمنع التكرار"""
        # إنشاء مفتاح فريد للطلب
        import urllib.parse
        log_key = f"{url}?{urllib.parse.urlencode(params)}"
        
        for attempt in range(max_retries):
            try:
                print(f"📡 API Request [{attempt+1}]: {log_key}")
                response = requests.get(url, headers=self.headers, params=params, timeout=15)
                print(f"📡 API Response [{response.status_code}]: {log_key}")
                
                if response.status_code == 200:
                    return response
                else:
                    print(f"⚠️ محاولة {attempt + 1} فشلت: {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"⚠️ محاولة {attempt + 1} فشلت: {e}")
            
            if attempt < max_retries - 1:
                time.sleep(1)
        
        return None

    def refresh_live_data_loop(self, dt):
        pass
    
    def _fetch_and_update_live_data(self):
        try:
            new_live_matches_data = self.fetch_live_matches_for_update()
            
            if new_live_matches_data:
                self.update_matches_data(new_live_matches_data)
                
            self.last_update = datetime.now().strftime('%H:%M:%S')
            
        except Exception as e:
            print(f"Error in auto-update: {e}")
            self.show_snackbar(f"Auto update error: {e}", duration=4)
            
    def fetch_live_matches_for_update(self):
        try:
            url = f"{self.base_url}/fixtures"
            params = {'live': 'all'}
            
            response = self.fetch_with_retry(url, params, max_retries=1)
            
            if response and response.status_code == 200:
                data = response.json()
                if data.get('response'):
                    matches = self.process_api_response_improved(data['response'])
                    live_matches = [match for match in matches if match.get('status') in ['1H', '2H', 'HT', 'ET', 'P', 'BT', 'LIVE']]

                    live_matches = self.filter_out_hidden_matches_immediately(live_matches)
                    
                    return live_matches
            return []
                
        except Exception as e:
            print(f"Error fetching live matches for update: {e}")
            return []

    @mainthread
    def update_matches_data(self, new_matches):
        hidden_ids = {m.get('id') for m in self.hidden_matches}

        filtered_new_matches = [
            match for match in new_matches 
            if match.get('id') not in hidden_ids
        ]
        
        print(f"🔄 تحديث البيانات: {len(new_matches)} مباراة جديدة، {len(new_matches) - len(filtered_new_matches)} مخفية")
        
        new_matches_dict = {m.get('id'): m for m in filtered_new_matches}
        
        updated_self_matches = []
        should_refresh_ui = False
        
        for old_match in self.matches:
            match_id = old_match.get('id')

            if match_id in hidden_ids:
                continue
                
            new_match = new_matches_dict.pop(match_id, None)
            
            if new_match:
                old_status = old_match.get('status')
                new_status = new_match.get('status')
                
                old_match.update(new_match)
                self.find_and_update_match_widget(old_match)
                
                updated_self_matches.append(old_match)
                
                if old_status in ['1H', '2H', 'HT', 'LIVE'] and new_status in ['FT', 'AET', 'PEN']:
                    should_refresh_ui = True
            else:
                updated_self_matches.append(old_match)

        for new_match_id, new_match in new_matches_dict.items():
            if new_match_id not in hidden_ids:
                updated_self_matches.append(new_match)
                should_refresh_ui = True
        
        self.matches = updated_self_matches
        self.today_matches = [m for m in self.matches if self._is_today(m.get('time'))]

        if should_refresh_ui and self.current_tab == 'live' and not self.calendar_mode:
            if self.current_filter != "No Filter":
                 self.run_filter_process_threaded() 
            else:
                 self.show_live_matches()
        
        self.root.ids.topbar.right_action_items[0][0] = 'update'
        Clock.schedule_once(lambda dt: self._reset_update_icon(), 2)
        
    def _reset_update_icon(self):
        self.root.ids.topbar.right_action_items[0][0] = 'autorenew'

    def find_and_update_match_widget(self, match_data):
        match_id = match_data.get('id')
        main_list = self.root.ids.main_list
        
        for widget in main_list.children:
            if isinstance(widget, OptimizedCompactMatchItem) and widget.match_data.get('id') == match_id:
                widget.match_data = match_data.copy()
                break

    def _is_today(self, time_str):
        if not time_str:
            return False
        try:
            match_date = datetime.fromisoformat(time_str.replace('Z', '+00:00')).date()
            return match_date == datetime.now().date()
        except:
            return False

    def get_required_league_ids(self):
        selected_league_ids = {l.get('id') for l in self.selected_leagues}
        favorite_league_ids = {l.get('id') for l in self.favorite_leagues}
        return selected_league_ids | favorite_league_ids

    @mainthread
    def update_popup_stats(self, popup, first_stats, second_stats, first_name_display, second_name_display, first_standings=None, second_standings=None):
        """تحديث إحصائيات البوب أب"""
        try:
            popup.first_team_name_display = first_name_display
            popup.second_team_name_display = second_name_display
            
            def extract_goals_and_color(stats):
                if stats is None:
                    return None, "N/A", "N/A"
                    
                if stats and ":" in stats:
                    parts = stats.split(":")
                    if len(parts) == 3:
                        return parts[0], parts[1], parts[2]
                return None, "N/A", "N/A"
            
            first_color, first_for, first_against = extract_goals_and_color(first_stats)
            if first_color is None:
                popup.first_team_color = "gray"
                popup.first_team_goals_for = "!"
                popup.first_team_goals_against = "!"
            else:
                popup.first_team_color = first_color
                popup.first_team_goals_for = first_for
                popup.first_team_goals_against = first_against
            
            second_color, second_for, second_against = extract_goals_and_color(second_stats)
            if second_color is None:
                popup.second_team_color = "gray"
                popup.second_team_goals_for = "!"
                popup.second_team_goals_against = "!"
            else:
                popup.second_team_color = second_color
                popup.second_team_goals_for = second_for
                popup.second_team_goals_against = second_against
            
            if first_standings:
                popup.first_team_current_rank = str(first_standings.get('current_rank', 'N/A'))
                popup.first_team_last_rank = str(first_standings.get('last_rank', 'N/A'))
                popup.first_team_points = str(first_standings.get('points', 'N/A'))
                popup.first_team_played = str(first_standings.get('played', 'N/A'))
                popup.first_last_rank_color = str(first_standings.get('last_rank_type', 'normal'))
            else:
                popup.first_team_current_rank = 'N/A'
                popup.first_team_last_rank = 'N/A'
                popup.first_team_points = 'N/A'
                popup.first_team_played = 'N/A'
                popup.first_last_rank_color = 'normal'
            
            if second_standings:
                popup.second_team_current_rank = str(second_standings.get('current_rank', 'N/A'))
                popup.second_team_last_rank = str(second_standings.get('last_rank', 'N/A'))
                popup.second_team_points = str(second_standings.get('points', 'N/A'))
                popup.second_team_played = str(second_standings.get('played', 'N/A'))
                popup.second_last_rank_color = str(second_standings.get('last_rank_type', 'normal'))
            else:
                popup.second_team_current_rank = 'N/A'
                popup.second_team_last_rank = 'N/A'
                popup.second_team_points = 'N/A'
                popup.second_team_played = 'N/A'
                popup.second_last_rank_color = 'normal'
                
        except Exception as e:
            print(f"Error updating popup stats: {e}")

    def close_stats_popup(self, popup):
        anim = Animation(opacity=0, duration=0.3)
        anim.start(popup)
        Clock.schedule_once(lambda dt: self.root.ids.stats_popup_container.remove_widget(popup), 0.3)

    @mainthread
    def update_ui_with_matches(self, matches):
        try:
            filtered_matches = self.filter_out_hidden_and_favorite_matches(matches)
            
            self.matches = filtered_matches
            self.today_matches = [m for m in filtered_matches if self._is_today(m.get('time'))]
            self.api_available = True
            
            if self.current_tab == 'live' and not self.calendar_mode:
                pass 
                    
            self.show_snackbar(f"Loaded {len(filtered_matches)} live matches")
            
        except Exception:
            pass

    @mainthread
    def show_error_in_main_thread(self, error_msg):
        self.show_api_error(error_msg)

    @mainthread
    def show_no_matches_in_main_thread(self):
        self.show_no_live_matches()

    def show_loading(self, message="Loading...", progress=0, status=""):
        container = self.root.ids.main_list
        container.clear_widgets()
        loading_widget = LoadingWidget()
        loading_widget.loading_text = message
        loading_widget.progress_value = progress
        loading_widget.status_text = status if status else "Please wait..."
        container.add_widget(loading_widget)

    def show_api_error(self, error_msg=""):
        self.api_available = False
        container = self.root.ids.main_list
        container.clear_widgets()
        error_widget = ErrorWidget()
        error_widget.error_text = f"Error: {error_msg}" if error_msg else "Connection error"
        container.add_widget(error_widget)

    def show_no_live_matches(self):
        self.api_available = True
        container = self.root.ids.main_list
        container.clear_widgets()
        
        empty_item = TwoLineListItem(
            text="No live matches",
            secondary_text="No matches are currently live. Try again later.",
            theme_text_color='Secondary'
        )
        container.add_widget(empty_item)

    def organize_live_matches_by_minute(self, live_matches):
        if not live_matches:
            return []
        
        matches_by_minute = {}
        
        for match in live_matches:
            elapsed = match.get('elapsed', 0)
            status = match.get('status', '')
            
            if status in ['1H', '2H', 'LIVE']:
                if elapsed is not None:
                    if elapsed <= 15:
                        minute_group = '1-15'
                    elif elapsed <= 30:
                        minute_group = '16-30'
                    elif elapsed <= 45:
                        minute_group = '31-45'
                    elif elapsed <= 60:
                        minute_group = '46-60'
                    elif elapsed <= 75:
                        minute_group = '61-75'
                    else:
                        minute_group = '76+'
                else:
                    minute_group = 'LIVE'
            elif status == 'HT':
                minute_group = 'HT'
            elif status == 'ET':
                minute_group = 'ET'
            elif status == 'P':
                minute_group = 'PEN'
            else:
                minute_group = 'OTHER'
        
            if minute_group not in matches_by_minute:
                matches_by_minute[minute_group] = []
            matches_by_minute[minute_group].append(match)
        
        group_order = [
            '76+', '61-75', '46-60', 'HT', '31-45', '16-30', '1-15', 
            'ET', 'PEN', 'LIVE', 'OTHER' 
        ]
        
        organized_matches = []
        for group in group_order:
            if group in matches_by_minute:
                matches_by_minute[group].sort(key=lambda m: m.get('elapsed', 0), reverse=False)
                organized_matches.extend(matches_by_minute[group])
        
        return organized_matches

    def show_live_matches(self):
        if self.calendar_mode:
            return
            
        if not self.api_available:
            self.show_api_error()
            return
            
        container = self.root.ids.main_list
        container.clear_widgets()
        
        if self.current_filter != "No Filter" and self.filtered_matches:
            self.display_filtered_matches()
            return
            
        live_matches = [m for m in self.matches if m.get('status') in ['1H', '2H', 'HT', 'ET', 'P', 'BT', 'LIVE']]
        
        required_league_ids = self.get_required_league_ids()
        
        if required_league_ids:
            filtered_live_matches = [
                match for match in live_matches
                if match.get('league_id') in required_league_ids
            ]
        else:
            filtered_live_matches = live_matches

        final_matches_to_show = self.filter_out_hidden_and_favorite_matches(filtered_live_matches)
        print(f"📊 Live Matches: {len(live_matches)} -> {len(filtered_live_matches)} بعد فلترة الدوريات -> {len(final_matches_to_show)} بعد الإخفاء النهائي")
        
        organized_live_matches = self.organize_live_matches_by_minute(final_matches_to_show)

        if len(organized_live_matches) > 0:
            count_label = MDLabel(
                text=f"Live Matches: {len(organized_live_matches)}",
                font_style='Button',
                halign='center',
                theme_text_color='Primary',
                bold=True,
                size_hint_y=None,
                height=dp(30)
            )
            container.add_widget(count_label)
            
            filter_texts = []
            if len(self.selected_leagues) > 0:
                filter_texts.append(f"Selected: {len(self.selected_leagues)}")
            if len(self.favorite_leagues) > 0:
                 filter_texts.append(f"Favorites: {len(self.favorite_leagues)}")
                
            if required_league_ids:
                filter_info = MDLabel(
                    text=f"Leagues Filter (Active): { ' | '.join(filter_texts) }",
                    font_style='Caption',
                    halign='center',
                    theme_text_color='Secondary',
                    size_hint_y=None,
                    height=dp(20)
                )
                container.add_widget(filter_info)
            
            if organized_live_matches:
                live_header = OneLineListItem(text=f"🔴 LIVE MATCHES ({len(organized_live_matches)})")
                live_header.md_bg_color = get_color_from_hex("#FFEBEE")
                container.add_widget(live_header)
                
                for match in organized_live_matches:
                    item = OptimizedCompactMatchItem(
                        match_data=match, 
                        is_fav=self.is_favorite(match.get('id'))
                    )
                    container.add_widget(item)
            
            if not organized_live_matches:
                self.show_empty_message("No live matches currently")
        else:
            self.show_empty_message("No live matches currently")

    def populate_matches(self, matches_list, container):
        for match in matches_list:
            item = OptimizedCompactMatchItem(
                match_data=match, 
                is_fav=self.is_favorite(match.get('id'))
            )
            container.add_widget(item)

    def show_favorites(self):
        """عرض المباريات المفضلة - تم تحديثها لقراءة من قاعدة البيانات"""
        container = self.root.ids.main_list
        container.clear_widgets()
        
        # ✅ تحديث مهم: إعادة تحميل المفضلة من قاعدة البيانات
        self.load_favorites()  # تأكد من جلب أحدث البيانات
        
        # الآن favorites تحتوي على كل المباريات المحفوظة
        fav_matches_data = self.favorites.copy()  # نسخة من البيانات
        
        # 🔧 فصل المباريات المحفوظة تلقائياً عن المحفوظة يدوياً
        auto_saved_matches = [m for m in fav_matches_data if m.get('auto_saved_by_filter')]
        normal_fav_matches = [m for m in fav_matches_data if not m.get('auto_saved_by_filter')]
        
        has_favorites = len(fav_matches_data) > 0
        
        if has_favorites:
            # عرض المباريات المحفوظة تلقائياً أولاً
            if auto_saved_matches:
                auto_header = OneLineListItem(text="🤖 AUTO-SAVED BY FILTER")
                auto_header.md_bg_color = get_color_from_hex("#E1F5FE")
                container.add_widget(auto_header)
                
                for match in auto_saved_matches:
                    item = OptimizedCompactMatchItem(
                        match_data=match, 
                        is_fav=True  # ✅ تأكد أنها تعرض كـ favorite
                    )
                    # إضافة معلومة الفلتر
                    if match.get('auto_saved_by_filter'):
                        filter_info = MDLabel(
                            text=f"فلتر: {match.get('auto_saved_by_filter')} | {match.get('saved_at', '')}",
                            font_style='Caption',
                            theme_text_color='Secondary',
                            size_hint_y=None,
                            height=dp(20)
                        )
                        container.add_widget(filter_info)
                    container.add_widget(item)
            
            # عرض المباريات المحفوظة يدوياً
            if normal_fav_matches:
                matches_header = OneLineListItem(text="⭐ FAVORITE MATCHES (MANUAL)")
                matches_header.md_bg_color = get_color_from_hex("#FFF8E1")
                container.add_widget(matches_header)
                for match in normal_fav_matches:
                    item = OptimizedCompactMatchItem(
                        match_data=match, 
                        is_fav=True
                    )
                    container.add_widget(item)
            
            # عرض الدوريات المفضلة
            self.load_favorite_leagues()  # تأكد من جلب أحدث البيانات
            fav_leagues_data = self.favorite_leagues
            if fav_leagues_data:
                leagues_header = OneLineListItem(text="🏆 FAVORITE LEAGUES")
                leagues_header.md_bg_color = get_color_from_hex("#E8F5E8")
                container.add_widget(leagues_header)
                
                for league in fav_leagues_data:
                    item = FavoriteLeagueItem(
                        league_name=league['name'],
                        league_id=league['id']
                    )
                    container.add_widget(item)
        else:
            self.show_empty_message("No favorites")

    def show_empty_message(self, message):
        container = self.root.ids.main_list
        container.clear_widgets()
        
        empty_item = TwoLineListItem(
            text=message,
            secondary_text="Please check other tabs or refresh.",
            theme_text_color='Secondary'
        )
        container.add_widget(empty_item)

    def update_time(self, *args):
        now = datetime.now()
        self.current_time = now.strftime('%H:%M - %d/%m/%Y')

    def switch_tab(self, tab_name):
        self.current_tab = tab_name
        self.update_nav_buttons()

        if tab_name == 'live':
            self.current_title = 'Live Matches'
            self.calendar_mode = False
            self.show_live_matches()
        elif tab_name == 'favorites':
            self.current_title = 'My Favorites'
            self.calendar_mode = False
            Clock.schedule_once(lambda dt: self.show_favorites(), 0.1)  # ✅ تحديث تلقائي
        elif tab_name == 'leagues':
            self.current_title = 'Leagues'
            self.calendar_mode = False
            self.show_leagues()
        elif tab_name == 'profile':
            self.current_title = 'My Profile'
            self.calendar_mode = False
            self.show_profile()

    def update_nav_buttons(self):
        tabs = {
            'live': 'btn_en_cours',
            'favorites': 'btn_favoris',
            'leagues': 'btn_competitions',
            'profile': 'btn_profil'
        }
        for tab_name, btn_id in tabs.items():
            self.root.ids[btn_id].selected = (tab_name == self.current_tab)

    def show_leagues(self):
        c = self.root.ids.main_list
        c.clear_widgets()

        box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=6)
        self.search_input = MDTextField(
            hint_text="Search for a league (ex: premier league, serie a)",
            size_hint_x=0.8
        )
        search_btn = MDFlatButton(
            text="Search",
            on_release=lambda x: self.fetch_leagues_threaded(self.search_input.text.strip().lower())
        )
        box.add_widget(self.search_input)
        box.add_widget(search_btn)
        c.add_widget(box)

        control_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=6)
        
        save_btn = MDRaisedButton(
            text="Save Selection",
            on_release=lambda x: self.save_selected_leagues(),
            size_hint_x=0.5
        )
        
        supreme_btn = MDRaisedButton(
            text="Supreme", 
            on_release=lambda x: self.save_supreme_selection(),
            size_hint_x=0.5,
            md_bg_color=get_color_from_hex("#000000")
        )
        
        control_box.add_widget(save_btn)
        control_box.add_widget(supreme_btn)
        c.add_widget(control_box)

        self.competitions_layout = MDGridLayout(cols=1, adaptive_height=True, spacing=10, padding=6)
        c.add_widget(self.competitions_layout)

        Clock.schedule_once(lambda dt: self.display_saved_leagues_for_selection(), 0.1)

    def display_saved_leagues_for_selection(self):
        layout = self.competitions_layout
        layout.clear_widgets()
        
        if not self.all_leagues:
            layout.add_widget(OneLineListItem(text="Please wait, loading leagues..."))
            return
            
        layout.add_widget(OneLineListItem(text="📋 PREVIOUSLY SELECTED LEAGUES"))
        
        current_selected_ids = {l.get('id') for l in self.selected_leagues}
        
        selected_leagues_info = [
            (f"{l['name']} ({l.get('country_name', 'World')})", l['id']) 
            for l in self.all_leagues if l['id'] in current_selected_ids
        ]

        if not selected_leagues_info:
             layout.add_widget(OneLineListItem(text="No leagues selected."))
             return

        for name, lid in selected_leagues_info:
            item = LeagueItem(league_name=name, league_id=lid)
            item.selected = True
            item.ids.check.icon = "checkbox-marked"
            layout.add_widget(item)

    def save_supreme_selection(self):
        layout = getattr(self, 'competitions_layout', None)
        if not layout:
            self.show_snackbar("⚠️ Interface error (Leagues)")
            return

        leagues_in_ui = [child for child in layout.children if isinstance(child, LeagueItem)]
        
        newly_selected_leagues_data = []
        deselected_leagues_ids = []
        
        for item in leagues_in_ui:
            if item.selected:
                league_data = {
                    'name': item.text,
                    'id': item.league_id
                }
                newly_selected_leagues_data.append(league_data)
            else:
                deselected_leagues_ids.append(item.league_id)

        current_selected = [l for l in self.selected_leagues if l['id'] not in deselected_leagues_ids]
        
        current_ids = {l['id'] for l in current_selected}
        
        for league in newly_selected_leagues_data:
            if league['id'] not in current_ids:
                current_selected.append(league)
                
        self.selected_leagues = current_selected
        self.save_league_selection()  
        message = f"✅ Supreme update successful: {len(self.selected_leagues)} leagues kept. (Removed: {len(deselected_leagues_ids)})"
        self.show_dialog(message)
        
        if self.current_tab == 'live':
            self.show_live_matches()
        
        self.display_saved_leagues_for_selection()

    def show_profile(self):
        container = self.root.ids.main_list
        container.clear_widgets()
        
        profile_header = OneLineListItem(text="👤 MY PROFILE")
        profile_header.md_bg_color = get_color_from_hex("#E8F5E8")
        container.add_widget(profile_header)
        
        stats_box = MDBoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(120))
        
        matches_count = len(self.favorites)
        leagues_count = len(self.favorite_leagues)
        hidden_count = len(self.hidden_matches)
        
        stats_box.add_widget(MDLabel(
            text=f"Favorite matches: {matches_count}",
            theme_text_color='Primary',
            halign='center'
        ))
        stats_box.add_widget(MDLabel(
            text=f"Favorite leagues: {leagues_count}",
            theme_text_color='Primary', 
            halign='center'
        ))
        stats_box.add_widget(MDLabel(
            text=f"Hidden matches: {hidden_count}",
            theme_text_color='Primary',
            halign='center'
        ))
        
        container.add_widget(stats_box)
        
        cache_box = MDBoxLayout(
            orientation='vertical', 
            spacing=dp(5), 
            size_hint_y=None, 
            height=dp(80),
            padding=dp(10)
        )
        
        cache_label = MDLabel(
            text="🗑️ CLEAR CACHE (Custom)",
            theme_text_color='Primary',
            halign='center',
            bold=True
        )
        cache_box.add_widget(cache_label)
        
        clear_cache_btn = MDRaisedButton(
            text="Clear Match, League & Goals Cache Only",
            size_hint_y=None,
            height=dp(40),
            md_bg_color=get_color_from_hex("#FF5252"),
            on_release=lambda x: self.show_clear_cache_dialog()
        )
        cache_box.add_widget(clear_cache_btn)
        
        container.add_widget(cache_box)
        
        filter_header = OneLineListItem(text="🎯 ADVANCED FILTER SYSTEM")
        filter_header.md_bg_color = get_color_from_hex("#E1F5FE")
        container.add_widget(filter_header)
        
        filter_buttons_box = MDBoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(320))
        
        btn_ns_filter = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40),
            padding=dp(5),
            spacing=dp(10)
        )
        btn_ns_filter_label = MDLabel(
            text="📅 ) N/A _last rank__ or__no last 3 Goals",
            theme_text_color='Primary',
            halign='left',
            valign='center',
            size_hint_x=0.8
        )
        btn_ns_filter_icon = MDIconButton(
            icon= "checkbox-marked" if self.filter_ns_perfect_1_1_enabled else "checkbox-blank-outline",
            theme_text_color='Custom',
            text_color=get_color_from_hex("#4CAF50") if self.filter_ns_perfect_1_1_enabled else get_color_from_hex("#757575"),
            on_release=lambda x: self.toggle_filter_ns_perfect_1_1(),
            size_hint_x=0.2
        )
        btn_ns_filter.add_widget(btn_ns_filter_label)
        btn_ns_filter.add_widget(btn_ns_filter_icon)
        filter_buttons_box.add_widget(btn_ns_filter)
        
        btn_ns_filter_2_2 = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40),
            padding=dp(5),
            spacing=dp(10)
        )
        btn_ns_filter_2_2_label = MDLabel(
            text="📅  FiLTER (Perfect 2_2) ORiGINAL",
            theme_text_color='Primary',
            halign='left',
            valign='center',
            size_hint_x=0.8
        )
        btn_ns_filter_2_2_icon = MDIconButton(
            icon= "checkbox-marked" if self.filter_ns_perfect_2_2_enabled else "checkbox-blank-outline",
            theme_text_color='Custom',
            text_color=get_color_from_hex("#4CAF50") if self.filter_ns_perfect_2_2_enabled else get_color_from_hex("#757575"),
            on_release=lambda x: self.toggle_filter_ns_perfect_2_2(),
            size_hint_x=0.2
        )
        btn_ns_filter_2_2.add_widget(btn_ns_filter_2_2_label)
        btn_ns_filter_2_2.add_widget(btn_ns_filter_2_2_icon)
        filter_buttons_box.add_widget(btn_ns_filter_2_2)
        
        btn_condition1 = MDRaisedButton(
            text="🔍 Condition 1: One Team Scored/No Goals",
            on_release=lambda x: self.apply_filter_condition_1(),
            size_hint_y=None,
            height=dp(40)
        )
        filter_buttons_box.add_widget(btn_condition1)
        
        btn_condition2 = MDRaisedButton(
            text="🎯 Condition 2: Loser Scored More (Last 3)",
            on_release=lambda x: self.apply_filter_condition_2(),
            size_hint_y=None,
            height=dp(40)
        )
        filter_buttons_box.add_widget(btn_condition2)
        
        btn_combined_1_2 = MDRaisedButton(
            text="⭐ Condition  (1) +  (2) ⭐",
            on_release=lambda x: self.apply_combined_filter_1_and_2(),
            size_hint_y=None,
            height=dp(40),
            md_bg_color=get_color_from_hex("#00A0B0")
        )
        filter_buttons_box.add_widget(btn_combined_1_2)
        
        btn_reset = MDFlatButton(
            text="🔄 Reset All Filters",
            on_release=lambda x: self.reset_all_filters(),
            size_hint_y=None,
            height=dp(40)
        )
        filter_buttons_box.add_widget(btn_reset)
        
        container.add_widget(filter_buttons_box)
        
        settings_header = OneLineListItem(text="⚙️ SETTINGS")
        settings_header.md_bg_color = get_color_from_hex("#F3E5F5")
        container.add_widget(settings_header)
        
        hidden_matches_btn = OneLineIconListItem(
            text="👻 Manage Hidden Matches",
            on_release=lambda x: self.show_hidden_matches(),
            bg_color=get_color_from_hex("#FFFFFF")
        )
        container.add_widget(hidden_matches_btn)
        
        info_header = OneLineListItem(text="ℹ️ ABOUT")
        info_header.md_bg_color = get_color_from_hex("#E3F2FD")
        container.add_widget(info_header)
        
        container.add_widget(OneLineListItem(text="📱 Version: 1.0.0"))
        container.add_widget(OneLineListItem(text="⚽ Football Live App"))
        container.add_widget(OneLineListItem(text="👨‍💻 Developed with KivyMD"))
    
    def show_clear_cache_dialog(self):
        """عرض حوار تأكيد مسح الكاش"""
        self.cache_dialog = MDDialog(
            title="🗑️ Clear Cache Confirmation",
            text="This will delete ONLY:\n\n• scheduled_matches_cache\n• league_standings_cache\n• scheduled_teams_goals_cache\n\n⚠️ Last season cache will NOT be affected\n⚠️ User data (favorites, hidden, etc.) will NOT be deleted",
            buttons=[
                MDFlatButton(
                    text="Cancel",
                    theme_text_color="Custom",
                    text_color=get_color_from_hex("#757575"),
                    on_release=lambda x: self.cache_dialog.dismiss()
                ),
                MDRaisedButton(
                    text="Clear Selected Cache",
                    md_bg_color=get_color_from_hex("#FF5252"),
                    on_release=lambda x: self.execute_clear_cache()
                )
            ]
        )
        self.cache_dialog.open()
    
    def execute_clear_cache(self):
        """تنفيذ مسح الكاش المحدد"""
        try:
            if hasattr(self, 'cache_dialog'):
                self.cache_dialog.dismiss()
            
            tables_to_clear = [
                'scheduled_matches_cache', 
                'league_standings_cache',
                'scheduled_teams_goals_cache'
            ]
            
            success, cleared_tables = self.storage.clear_specific_cache(tables=tables_to_clear)
            
            if success:
                self.scheduled_teams_goals_cache = {}
                self.scheduled_teams_loading = {}
                
                self.show_snackbar(f"✅ Cache cleared: {', '.join(cleared_tables)}", duration=4)
                
                try:
                    conn = self.storage.get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute("SELECT COUNT(*) FROM last_season_standings_cache")
                    last_season_count = cursor.fetchone()[0]
                    
                    conn.close()
                    
                    if last_season_count > 0:
                        print(f"✅ Last season cache preserved: {last_season_count} records")
                        self.show_snackbar(f"✅ الموسم الماضي محفوظ ({last_season_count} دوري)", duration=3)
                    else:
                        print("ℹ️ No last season cache found")
                        
                except Exception as e:
                    print(f"⚠️ Error checking last season cache: {e}")
            else:
                self.show_snackbar("❌ Failed to clear cache", duration=4)
                
        except Exception as e:
            print(f"❌ Error in clear cache: {e}")
            self.show_snackbar(f"❌ Error: {str(e)}", duration=4)
    
    def reset_all_filters(self):
        """إعادة تعيين جميع الفلترات"""
        self.reset_filter()
        self.filter_ns_perfect_1_1_enabled = False
        self.filter_ns_perfect_2_2_enabled = False
        
        self.save_filter_state()
        
        if self.current_tab == 'profile':
            self.show_profile()
        elif self.current_tab == 'live':
            self.show_live_matches()
            
        self.show_snackbar("✅ All filters reset")

    def show_hidden_matches(self):
        container = self.root.ids.main_list
        container.clear_widgets()
        
        if self.hidden_matches:
            header = OneLineListItem(text="👻 HIDDEN MATCHES")
            header.md_bg_color = get_color_from_hex("#F3E5F5")
            container.add_widget(header)
            
            for match in self.hidden_matches:
                item = OptimizedCompactMatchItem(
                    match_data=match, 
                    is_fav=self.is_favorite(match.get('id'))
                )
                container.add_widget(item)
            
            clear_btn = MDRaisedButton(
                text="Clear All Hidden Matches",
                pos_hint={'center_x': 0.5},
                size_hint_x=0.8,
                on_release=lambda x: self.clear_all_hidden_matches()
            )
            container.add_widget(clear_btn)
        else:
            self.show_empty_message("No hidden matches")

    def clear_all_hidden_matches(self):
        if self.hidden_matches:
            self.hidden_matches = []
            self.save_hidden_matches()
            self.show_snackbar("All hidden matches cleared permanently")
            
            if self.current_tab == 'profile':
                self.show_hidden_matches()
        else:
            self.show_snackbar("No hidden matches to clear")

    def fetch_leagues_threaded(self, keyword=""):
        future = self.executor.submit(self.fetch_leagues_api, keyword)
        self.futures.append(future)

    def fetch_leagues_api(self, keyword=""):
        url = "https://v3.football.api-sports.io/leagues"
        headers = {"x-apisports-key": "ff5507928d7ea3382d5a8149db14e988"}
        try:
            if self.leagues_loaded:
                 leagues = self.all_leagues
            else:
                resp = requests.get(url, headers=headers)
                data = resp.json()
                leagues = data.get("response", [])
            
            filtered = []

            for item in leagues:
                if isinstance(item, dict) and 'league' in item:
                    league = item.get("league", {})
                    country = item.get("country", {})
                else:
                    league = item
                    country = {'name': item.get('country_name', ''), 'code': item.get('country_code', '')}

                name = league.get("name", "")
                country_name = country.get("name", "")
                league_id = league.get("id", "")
                lname = name.lower()
                cname = country_name.lower()

                if keyword and keyword not in lname and keyword not in cname:
                    continue
                if any(x in lname for x in ["women", "feminine", "u19", "u20", "u17"]):
                    continue

                filtered.append((f"{name} ({country_name})", league_id))

            Clock.schedule_once(lambda dt: self.display_leagues(filtered))
        except Exception as e:
            print("⚠️ Loading error:", e)
            Clock.schedule_once(lambda dt: self.show_dialog("Error loading leagues"))

    def display_leagues(self, leagues_list):
        layout = self.competitions_layout
        layout.clear_widgets()

        if not leagues_list:
            layout.add_widget(OneLineListItem(text="No leagues found"))
            return

        layout.add_widget(OneLineListItem(text="📋 SEARCH RESULTS"))
        
        current_selected_ids = {l.get('id') for l in self.selected_leagues}
        
        for name, lid in leagues_list:
            item = LeagueItem(league_name=name, league_id=lid)
            
            if lid in current_selected_ids:
                item.selected = True
                item.ids.check.icon = "checkbox-marked"
            
            layout.add_widget(item)

    def save_selected_leagues(self):
        selected = []
        layout = getattr(self, 'competitions_layout', None)
        
        if layout:
            for child in layout.children:
                if isinstance(child, LeagueItem) and hasattr(child, 'selected') and child.selected:
                    selected.append({
                        'name': child.text,
                        'id': child.league_id
                    })

        if selected:
            old_data = self.selected_leagues.copy()

            merged = {item['id']: item for item in old_data}
            for league in selected:
                merged[league['id']] = league

            final_list = list(merged.values())

            self.selected_leagues = final_list
            self.save_league_selection()

            message = f"✅ {len(selected)} new leagues added! (Total: {len(final_list)})"
        else:
            message = "⚠️ No leagues selected"
        
        self.show_dialog(message)
        
        if self.current_tab == 'live':
            self.show_live_matches()

    def show_snackbar(self, message, duration=3):
        try:
            Snackbar(
                text=message,
                duration=duration,
                snackbar_x="10dp",
                snackbar_y="10dp",
                size_hint_x=(Window.width - (dp(10) * 2)) / Window.width,
                bg_color=get_color_from_hex("#323232")
            ).open()
        except Exception as e:
            print(f"Error showing snackbar: {e}")

    def show_dialog(self, text):
        self.dialog = MDDialog(
            title="Information",
            text=text,
            buttons=[MDFlatButton(text="OK", on_release=lambda x: self.dialog.dismiss())]
        )
        self.dialog.open()

    def open_menu(self):
        self.show_snackbar('Menu opened')

    def go_back(self):
        if self.calendar_mode:
            self.calendar_mode = False
            self.current_title = 'Live Matches'
            self.show_live_matches()
            self.show_snackbar('Back to live matches')
        else:
            self.show_snackbar('Back')

    def manual_refresh(self):
        self.refresh_data()
        self.show_snackbar('Manual refresh...')

    def toggle_auto_update(self):
        self.auto_update = not self.auto_update
        status = "enabled" if self.auto_update else "disabled"
        self.show_snackbar(f"Auto update {status}")
        
        if self.auto_update:
            if not self._update_event:
                self._update_event = Clock.schedule_interval(self.refresh_live_data_loop, self.update_interval)
            elif not self._update_event.is_active:
                self._update_event()
        else:
            if self._update_event:
                self._update_event.cancel()

    def show_hidden_matches_in_profile(self):
        if self.current_tab == 'profile':
            self.show_profile()

    def retry_loading(self):
        self.load_leagues_and_matches()

    def refresh_data(self):
        future = self.executor.submit(self._fetch_and_update_live_data)
        self.futures.append(future)

    def default_filter_condition(self, match_data):
        return "❌ no"
        
    def filter_condition_1(self, match_data):
        try:
            home_score = match_data.get('home_score', 0)
            away_score = match_data.get('away_score', 0)
            status = match_data.get('status', '')
            
            if status not in ['NS', '1H', '2H', 'HT', 'ET', 'LIVE']:
                 return "❌ no"
            
            if status == 'NS':
                return "✅ yes"
            
            if (home_score > 0 and away_score == 0) or (home_score == 0 and away_score > 0):
                return "✅ yes"
            
            if home_score == 0 and away_score == 0:
                return "✅ yes"
            
            return "❌ no"
        except Exception as e:
            print(f"Error in filter_condition_1: {e}")
            return "❌ no"

    def extract_goals_for_and_against(self, stats_str):
        """استخراج الأهداف مع معالجة None"""
        try:
            if not stats_str or stats_str is None:
                return None, None

            stats_str = stats_str.strip()

            parts = stats_str.split(":")

            if len(parts) != 3:
                return None, None

            if not (parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit()):
                return None, None
            
            goals_for = int(parts[1])
            goals_against = int(parts[2])
            
            return goals_for, goals_against
            
        except Exception as e:
            print(f"Error extracting goals from '{stats_str}': {e}")
            return None, None

    def filter_condition_2(self, match_data):
        """فلتر الشرط 2 مع استخدام الكاش المحسن"""
        try:
            home_team_id = match_data.get('home_team_id')
            away_team_id = match_data.get('away_team_id')
            league_id = match_data.get('league_id')
            season = match_data.get('season')
            
            if not season:
                season = datetime.now().year
                
            home_score = match_data.get('home_score', 0)
            away_score = match_data.get('away_score', 0)
            status = match_data.get('status', 'NS')
            
            time_str = match_data.get('time', '')
            match_date = ""
            if time_str:
                try:
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    match_date = dt.strftime('%Y-%m-%d')
                except:
                    match_date = datetime.now().strftime('%Y-%m-%d')
            
            scheduled_cache = self.storage.load_scheduled_matches_from_cache(match_date, league_id)
            
            if scheduled_cache:
                match_found = any(
                    m.get('home_team_id') == home_team_id and 
                    m.get('away_team_id') == away_team_id 
                    for m in scheduled_cache
                )
                if not match_found:
                    return "❌ no (المباراة غير مجدولة)"
            else:
                return "❌ no (لا يوجد كاش)"
            
            if status in ['FT', 'AET', 'PEN']:
                if home_score == 0 and away_score == 0:
                    return "❌ no"
                return "❌ no"
            
            if home_score > 0 and away_score > 0:
                return "❌ no"
            
            if status not in ['NS', '1H', '2H', 'HT', 'ET', 'LIVE']:
                return "❌ no"
            
            if status == 'NS':
                return "✅ yes"
            
            if home_score == away_score and status != 'NS': 
                return "✅ yes"
            
            if not home_team_id or not away_team_id or not league_id:
                return "❌ no"
            
            if home_score < away_score:
                losing_team_id = home_team_id
                winning_team_id = away_team_id
                losing_is_home = True
            else: 
                losing_team_id = away_team_id
                winning_team_id = home_team_id
                losing_is_home = False
            
            # ⭐ استخدام الكاش المحسن
            losing_stats_dict = self.get_team_goals_from_cache(losing_team_id, league_id, season, losing_is_home, match_date)
            winning_stats_dict = self.get_team_goals_from_cache(winning_team_id, league_id, season, not losing_is_home, match_date)
            
            losing_goals_for = losing_stats_dict.get('goals_for', 0) if losing_stats_dict else 0          
            winning_goals_for = winning_stats_dict.get('goals_for', 0) if winning_stats_dict else 0            
            
            if losing_goals_for >= winning_goals_for:
                return "✅ yes"
            
            return "❌ no"
            
        except Exception as e:
            return "❌ no"

    def combined_filter_condition(self, match_data):
        condition1_result = self.filter_condition_1(match_data)
        condition2_result = self.filter_condition_2(match_data)
        
        if condition1_result == "✅ yes" and condition2_result == "✅ yes":
            return "✅ yes"
        
        return "❌ no"
        
    def filter_condition_combined_1_and_2(self, match_data):
        condition1_result = self.filter_condition_1(match_data)
        if condition1_result != "✅ yes":
            return "❌ no"

        condition2_result = self.filter_condition_2(match_data)
        
        if condition2_result == "✅ yes":
            return "✅ yes"
        
        return "❌ no"

    def apply_filter_condition_1(self):
        self.set_filter_logic(self.filter_condition_1, "One Team Scored/No Goals")
        self.run_filter_process_threaded()
        self.show_snackbar("Applied Condition 1: One team scored or no goals")

    def apply_filter_condition_2(self):
        self.set_filter_logic(self.filter_condition_2, "Loser Scored More (Last 3)")
        self.run_filter_process_threaded()
        self.show_snackbar("Applied Condition 2: Losing team scored more in last 3 matches")

    def apply_combined_filter(self):
        self.set_filter_logic(self.combined_filter_condition, "Combined Filter (1 and 2)")
        self.run_filter_process_threaded()
        self.show_snackbar("Applied Combined Filter (Conditions 1 and 2)")

    def apply_combined_filter_1_and_2(self):
        self.set_filter_logic(self.filter_condition_combined_1_and_2, "Condition 1 + 2")
        self.run_filter_process_threaded()
        self.show_snackbar("Applied Combined Filter: One Team Scored/No Goals AND Loser Stats")
    
    def apply_combined_filter_on_start(self):
        self.set_filter_logic(self.filter_condition_combined_1_and_2, "Condition 1 + 2 (Auto)")
        Clock.schedule_once(lambda dt: self.run_filter_process_threaded(), 0)
        self.show_snackbar("Auto-Filter Applied: Condition 1 + 2")

    def reset_filter_ui(self):
        self.reset_filter()
        if self.current_tab == 'live':
            self.show_live_matches()
        self.show_snackbar("Filter reset")

    def set_filter_logic(self, new_logic_function, filter_name="Custom"):
        self.filter_condition = new_logic_function
        self.current_filter = filter_name

    def run_filter_process_threaded(self):
        if self._is_filtering:
            return
            
        self._is_filtering = True
        
        future = self.executor.submit(self._apply_filter_process)
        self.futures.append(future)
        
    def _apply_filter_process(self):
        """دالة مساعدة لتطبيق الفلتر في ThreadPoolExecutor"""
        try:
            filtered_matches = []
            filter_results = {}
            
            live_matches = self.fetch_live_matches_sync()
            
            relevant_matches = [
                match for match in live_matches 
                if match.get('status') in ['1H', '2H', 'HT', 'ET', 'P', 'BT', 'LIVE']
            ]
            
            required_league_ids = self.get_required_league_ids()
            if required_league_ids:
                relevant_matches = [
                    match for match in relevant_matches
                    if match.get('league_id') in required_league_ids
                ]

            hidden_ids = {m.get('id') for m in self.hidden_matches}
            relevant_matches = [
                match for match in relevant_matches 
                if match.get('id') not in hidden_ids
            ]
            
            for match in relevant_matches:
                match_id = match.get('id')
                result = self.apply_filter_condition(match)
                filter_results[match_id] = result
                
                if result == "✅ yes":
                    filtered_matches.append(match)
            
            Clock.schedule_once(lambda dt: self._update_ui_with_filtered_matches(
                filtered_matches, filter_results
            ), 0)
            
        except Exception as e:
            print(f"Filter error: {e}")
            Clock.schedule_once(lambda dt: self._handle_filter_error(e), 0)

    def apply_filter_condition(self, match_data):
        return self.filter_condition(match_data)

    @mainthread
    def _update_ui_with_filtered_matches(self, filtered_matches, filter_results):
        self.filtered_matches = filtered_matches
        self.filter_results = filter_results
        self._is_filtering = False
        
        if self.current_tab == 'live' and not self.calendar_mode:
            self.display_filtered_matches()

    def display_filtered_matches(self):
        container = self.root.ids.main_list
        container.clear_widgets()
        
        if self._is_filtering:
            self.show_loading("Applying filter...")
            return

        hidden_ids = {m.get('id') for m in self.hidden_matches}
        final_filtered_matches = [
            match for match in self.filtered_matches 
            if match.get('id') not in hidden_ids
        ]
            
        if final_filtered_matches:
            filter_info = MDLabel(
                text=f"🔍 Active Filter: {self.current_filter} | Live Matches: {len(final_filtered_matches)}",
                font_style='Button',
                halign='center',
                theme_text_color='Primary',
                bold=True,
                size_hint_y=None,
                height=dp(30)
            )
            container.add_widget(filter_info)
            
            organized_live_matches = self.organize_live_matches_by_minute(final_filtered_matches)
            
            if organized_live_matches:
                live_header = OneLineListItem(text=f"🔴 LIVE MATCHES ({len(organized_live_matches)})")
                live_header.md_bg_color = get_color_from_hex("#FFEBEE")
                container.add_widget(live_header)
                
                for match in organized_live_matches:
                    item = OptimizedCompactMatchItem(match_data=match)
                    container.add_widget(item)
            
            if not organized_live_matches:
                 self.show_empty_message("No live matches match filter conditions")

        else:
            self.show_empty_message("No live matches match filter conditions")

    def check_single_match_condition(self, match_data):
        match_id = match_data.get('id')
        
        if match_id in self.filter_results:
            return self.filter_results[match_id]
        
        result = self.apply_filter_condition(match_data)
        self.filter_results[match_id] = result
        
        return result

    def reset_filter(self):
        self.filtered_matches = []
        self.filter_results = {}
        self._is_filtering = False
        self.filter_condition = self.default_filter_condition
        self.current_filter = "No Filter"

    def clear_filter_cache(self):
        self.filter_results.clear()

    def start_filtering(self):
        self._is_filtering = True
        self.show_loading("Applying filter...")

    def stop_filtering(self):
        self._is_filtering = False

    def schedule_auto_filter(self, interval=None):
        if interval:
            self.filter_interval = interval
        
        if self._auto_filter_event:
            self._auto_filter_event.cancel()
        
        self._auto_filter_event = Clock.schedule_interval(
            lambda dt: self.run_filter_process_threaded(), 
            self.filter_interval
        )

    def _handle_filter_error(self, error):
        self._is_filtering = False
        self.show_snackbar(f"Filter error: {error}")

    def load_leagues_and_matches(self):
        self.show_loading("🚀 Starting Football App", 0, "Initializing...")
        
        future = self.executor.submit(self._load_with_progress)
        self.futures.append(future)

    def _load_with_progress(self):
        total_steps = 5
        current_step = 0
        
        try:
            current_step += 1
            progress = (current_step / total_steps) * 100
            self.update_loading_status(progress, "🔌 Connecting to server...")
            time.sleep(0.5)
            
            current_step += 1
            progress = (current_step / total_steps) * 100
            self.update_loading_status(progress, "🏆 Loading leagues...")
            leagues = self.fetch_leagues()
            
            if leagues:
                current_step += 1
                progress = (current_step / total_steps) * 100
                self.update_loading_status(progress, "📊 Processing data...")
                self.all_leagues = leagues
                self.leagues_loaded = True
                
                current_step += 1
                progress = (current_step / total_steps) * 100
                self.update_loading_status(progress, "⚽ Loading live matches...")
                live_matches = self.fetch_live_matches_sync()
                
                current_step += 1
                progress = (current_step / total_steps) * 100
                self.update_loading_status(progress, "🎯 Applying filters...")
                
                if live_matches:
                    self.update_ui_with_matches(live_matches)
                    self.apply_combined_filter_on_start()
                else:
                    self.show_no_matches_in_main_thread()
            else:
                self.show_error_in_main_thread("Could not load leagues")
                
            self.update_loading_status(100, "✅ Ready!")
            time.sleep(0.3)
            
        except Exception as e:
            self.show_error_in_main_thread(str(e))
        finally:
            self._is_loading = False

    @mainthread
    def update_loading_status(self, progress, status):
        container = self.root.ids.main_list
        for widget in container.children:
            if isinstance(widget, LoadingWidget):
                widget.progress_value = progress
                widget.status_text = status
                break

    def actualaser_refresh(self):
        self._animate_refresh_button()
        
        self.show_snackbar("🔄 Actualaser - Quick Refresh")
        
        if self.current_filter != "No Filter":
            self.run_filter_process_threaded()
        else:
            future = self.executor.submit(self._quick_refresh)
            self.futures.append(future)

    def _animate_refresh_button(self):
        try:
            self.show_snackbar("⚡ Refreshing...")
        except:
            pass

    def _quick_refresh(self):
        try:
            self.show_loading("Quick Refresh...", 0, "Updating data...")
            
            new_matches = self.fetch_live_matches_for_update()
            if new_matches:
                self.update_matches_data(new_matches)
                self.show_snackbar("✅ Data updated successfully")
            else:
                self.show_snackbar("⚠️ No new data available")
                
        except Exception as e:
            self.show_snackbar(f"❌ Refresh error: {str(e)}")


if __name__ == '__main__':
    ProfessionalFootballApp().run()
