[app]
# Android package metadata
title = Mana Illu Rental Manager
package.name = manailu
package.domain = com.rentalmanager
source.dir = .
source.include_exts = py,db,png,jpg,kv,xlsx,ttf
version = 0.1.0
# Pillow's Android recipe pulls in freetype and harfbuzz for font shaping.
# libraqm is not an upstream python-for-android recipe, so do not list it
# directly or the Buildozer build will fail with an unknown recipe error.
requirements = python3,kivy==2.3.1,pyjnius,Pillow,freetype,harfbuzz
orientation = portrait
fullscreen = 0

# Android permissions for the future reminder/SMS integration.
android.permissions = INTERNET,SEND_SMS
android.api = 33
android.minapi = 23

[buildozer]
log_level = 2
warn_on_root = 1
