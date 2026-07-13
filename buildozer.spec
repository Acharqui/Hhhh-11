[app]

# (str) Title of your application
title = livescore

# (str) Package name
package.name = livescore

# (str) Package domain (needed for android/ios packaging)
package.domain = org.chaib11100

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,ttf,json

# (list) Source files to exclude (let empty to not exclude anything)
#source.exclude_exts = spec

# (str) Application versioning
version = 0.5
android.version_code = 5

# (list) Application requirements - تم إصلاح التوافق
requirements = python3==3.10.0,kivy==2.3.0,kivymd==1.2.0,requests,certifi,urllib3,chardet,idna,pyjnius

# (str) Presplash of the application (اختياري)
#presplash.filename = data/presplash.png

# (str) Icon of the application
icon.filename = Image.png

# (list) Supported orientations
orientation = portrait

#
# Android specific
#

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE,ACCESS_NETWORK_STATE

# (int) Target Android API
android.api = 30

# (int) Minimum API your APK will support
android.minapi = 21

# (str) Android NDK version to use - إصدار مستقر مع Python 3.10
android.ndk = 23.2.8568313

# (int) Android NDK API
android.ndk_api = 21

# (bool) Use --private data storage
android.private_storage = True

# (bool) If True, then skip trying to update the Android sdk
android.skip_update = False

# (bool) If True, then automatically accept SDK license
android.accept_sdk_license = True

# (str) Android entry point
android.entrypoint = org.kivy.android.PythonActivity

# (str) Android app theme
android.apptheme = "@android:style/Theme.NoTitleBar"

# (bool) Enable AndroidX support - مهم لـ KivyMD
android.enable_androidx = True

# (list) Gradle dependencies لـ KivyMD
android.gradle_dependencies = androidx.recyclerview:recyclerview:1.2.1,androidx.cardview:cardview:1.0.0,com.google.android.material:material:1.5.0

# (bool) Indicate whether the screen should stay on
android.wakelock = False

# (bool) enables Android auto backup feature
android.allow_backup = True

# (list) The Android archs to build for
android.archs = arm64-v8a, armeabi-v7a

# (str) XML file to include as an intent filters in <activity> tag
android.manifest.intent_filters = 

# (str) Extra xml to write directly inside the <manifest> element
android.manifest.uses_permission = android.permission.MANAGE_EXTERNAL_STORAGE

# (str) Android SDK directory
android.sdk_path = /home/runner/.buildozer/android/platform/android-sdk

# (str) Android NDK directory
android.ndk_path = /home/runner/.buildozer/android/platform/android-ndk-r23b

# (str) ANT directory
android.ant_path = /home/runner/.buildozer/android/platform/apache-ant-1.9.4

#
# Python for android (p4a) specific
#

# (str) python-for-android branch to use
p4a.branch = master

# (str) Bootstrap to use for android builds
p4a.bootstrap = sdl2

# (bool) Control passing the --use-setup-py vs --ignore-setup-py to p4a
p4a.setup_py = false

# (str) extra command line arguments to pass when invoking pythonforandroid.toolchain
p4a.extra_args = --debug

#
# OSX Specific
#

osx.python_version = 3
osx.kivy_version = 2.3.0

#
# iOS specific
#

ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master
ios.ios_deploy_url = https://github.com/phonegap/ios-deploy
ios.ios_deploy_branch = 1.10.0
ios.codesign.allowed = false

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 1

# إعدادات التوقيع
android.signing.keyalias = chaib11100
android.signing.keypassword = chaib11100
android.signing.storepass = chaib11100
android.signing.storefile = my-release-key.keystore
