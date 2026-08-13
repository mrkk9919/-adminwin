package com.wingbank.mobile

import android.app.Application
import com.wingbank.mobile.fcm.PushManager
import com.wingbank.mobile.utils.NotificationHelper

/**
 * Wing Bank Application
 * 应用入口，初始化各种服务
 */
class WingBankApplication : Application() {

    override fun onCreate() {
        super.onCreate()

        // 初始化通知渠道
        NotificationHelper.initChannels(this)

        // 初始化推送管理器
        PushManager.init(this)

        // 检查并刷新 token
        PushManager.checkAndRefreshToken()

        // 可选：订阅全局主题（用于广播通知）
        // PushManager.subscribeToTopic("all_users")
    }
}
