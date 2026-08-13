package com.wingbank.mobile.utils

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationCompat
import com.wingbank.mobile.R

/**
 * NotificationHelper - 通知工具类
 * 用于创建通知渠道、构建通知等
 */
object NotificationHelper {

    // 通知渠道 ID
    const val CHANNEL_TRANSACTIONS = "wingbank_transactions"
    const val CHANNEL_SECURITY = "wingbank_security"
    const val CHANNEL_PROMOTIONS = "wingbank_promotions"
    const val CHANNEL_DEFAULT = "wingbank_default"

    /**
     * 初始化所有通知渠道
     * 在 Application.onCreate 中调用
     */
    fun initChannels(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return
        }

        val notificationManager =
            context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        // 交易通知渠道
        val transactionChannel = NotificationChannel(
            CHANNEL_TRANSACTIONS,
            context.getString(R.string.channel_transactions),
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = context.getString(R.string.channel_transactions_desc)
            enableVibration(true)
            vibrationPattern = longArrayOf(100, 200, 100, 200)
            enableLights(true)
            lightColor = context.getColor(R.color.primary)
        }

        // 安全通知渠道
        val securityChannel = NotificationChannel(
            CHANNEL_SECURITY,
            context.getString(R.string.channel_security),
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = context.getString(R.string.channel_security_desc)
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 500, 200, 500)
            enableLights(true)
            lightColor = context.getColor(R.color.error)
        }

        // 营销通知渠道
        val promotionsChannel = NotificationChannel(
            CHANNEL_PROMOTIONS,
            context.getString(R.string.channel_promotions),
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = context.getString(R.string.channel_promotions_desc)
            enableVibration(false)
        }

        // 默认通知渠道
        val defaultChannel = NotificationChannel(
            CHANNEL_DEFAULT,
            context.getString(R.string.channel_default),
            NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
            description = context.getString(R.string.channel_default_desc)
        }

        // 创建所有渠道
        notificationManager.createNotificationChannels(
            listOf(
                transactionChannel,
                securityChannel,
                promotionsChannel,
                defaultChannel
            )
        )
    }

    /**
     * 检查通知权限（Android 13+）
     */
    fun hasNotificationPermission(context: Context): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            context.checkSelfPermission(
                android.Manifest.permission.POST_NOTIFICATIONS
            ) == android.content.pm.PackageManager.PERMISSION_GRANTED
        } else {
            true // Android 12 及以下默认有通知权限
        }
    }

    /**
     * 检查特定渠道是否开启通知
     */
    fun isChannelEnabled(context: Context, channelId: String): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return true
        }

        val notificationManager =
            context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        val channel = notificationManager.getNotificationChannel(channelId)
        return channel?.importance != NotificationManager.IMPORTANCE_NONE
    }

    /**
     * 打开应用通知设置页面
     */
    fun openNotificationSettings(context: Context) {
        val intent = android.content.Intent()
        intent.action = "android.settings.APP_NOTIFICATION_SETTINGS"
        intent.putExtra("android.provider.extra.APP_PACKAGE", context.packageName)
        intent.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
    }

    /**
     * 构建简单通知
     */
    fun buildNotification(
        context: Context,
        channelId: String,
        title: String,
        body: String,
        icon: Int = R.drawable.ic_notification
    ): NotificationCompat.Builder {
        return NotificationCompat.Builder(context, channelId)
            .setSmallIcon(icon)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
    }
}
