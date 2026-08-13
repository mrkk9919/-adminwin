package com.wingbank.mobile.fcm

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.RingtoneManager
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.wingbank.mobile.MainActivity
import com.wingbank.mobile.R
import com.wingbank.mobile.ui.transaction.TransactionDetailActivity

/**
 * Wing Bank Firebase Messaging Service
 * 处理 FCM 推送消息的接收和展示
 */
class WingFirebaseMessagingService : FirebaseMessagingService() {

    companion object {
        private const val TAG = "WingFCM"

        // 通知渠道 ID
        const val CHANNEL_TRANSACTIONS = "wingbank_transactions"
        const val CHANNEL_SECURITY = "wingbank_security"
        const val CHANNEL_DEFAULT = "wingbank_default"

        // 通知类型
        const val TYPE_TRANSFER_RECEIVED = "transfer_received"
        const val TYPE_TRANSFER_SENT = "transfer_sent"
        const val TYPE_BALANCE_UPDATE = "balance_update"
        const val TYPE_SECURITY_ALERT = "security_alert"
        const val TYPE_TEST = "test"
    }

    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        Log.d(TAG, "From: ${remoteMessage.from}")

        // 检查是否包含通知负载
        remoteMessage.notification?.let { notification ->
            Log.d(TAG, "Notification Title: ${notification.title}")
            Log.d(TAG, "Notification Body: ${notification.body}")

            // 解析数据负载
            val type = remoteMessage.data["type"] ?: TYPE_DEFAULT
            val transactionId = remoteMessage.data["transaction_id"]
            val amount = remoteMessage.data["amount"]
            val currency = remoteMessage.data["currency"]

            // 显示通知
            sendNotification(
                title = notification.title ?: getString(R.string.app_name),
                body = notification.body ?: "",
                type = type,
                transactionId = transactionId,
                data = remoteMessage.data
            )
        }

        // 如果只有数据负载，没有通知负载，也处理一下
        if (remoteMessage.notification == null && remoteMessage.data.isNotEmpty()) {
            val type = remoteMessage.data["type"] ?: TYPE_DEFAULT
            val title = remoteMessage.data["title"] ?: getString(R.string.app_name)
            val body = remoteMessage.data["body"] ?: ""

            sendNotification(
                title = title,
                body = body,
                type = type,
                transactionId = remoteMessage.data["transaction_id"],
                data = remoteMessage.data
            )
        }
    }

    override fun onNewToken(token: String) {
        Log.d(TAG, "Refreshed token: $token")

        // 将新 token 发送到后端
        PushManager.sendTokenToServer(token)
    }

    /**
     * 发送通知
     */
    private fun sendNotification(
        title: String,
        body: String,
        type: String,
        transactionId: String?,
        data: Map<String, String>
    ) {
        // 创建通知点击意图
        val intent = createNotificationIntent(type, transactionId, data)

        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_IMMUTABLE
        )

        // 根据类型选择通知渠道
        val channelId = getChannelId(type)

        // 获取通知声音
        val defaultSoundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)

        // 构建通知
        val notificationBuilder = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .setSound(defaultSoundUri)
            .setContentIntent(pendingIntent)
            .setPriority(getNotificationPriority(type))
            .setDefaults(NotificationCompat.DEFAULT_ALL)

        // 添加大文本样式（长内容时可展开）
        notificationBuilder.setStyle(
            NotificationCompat.BigTextStyle().bigText(body)
        )

        val notificationManager =
            getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        // Android 8.0+ 需要创建通知渠道
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            createNotificationChannels(notificationManager)
        }

        // 使用唯一 ID 显示通知
        val notificationId = generateNotificationId(type)
        notificationManager.notify(notificationId, notificationBuilder.build())

        Log.d(TAG, "Notification sent: type=$type, id=$notificationId")
    }

    /**
     * 创建通知点击意图
     */
    private fun createNotificationIntent(
        type: String,
        transactionId: String?,
        data: Map<String, String>
    ): Intent {
        return when (type) {
            TYPE_TRANSFER_RECEIVED, TYPE_TRANSFER_SENT -> {
                // 跳转到交易详情页
                Intent(this, TransactionDetailActivity::class.java).apply {
                    putExtra("transaction_id", transactionId)
                    putExtra("notification_type", type)
                    addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                }
            }
            TYPE_SECURITY_ALERT -> {
                // 跳转到安全中心
                Intent(this, MainActivity::class.java).apply {
                    putExtra("navigate_to", "security")
                    addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                }
            }
            TYPE_BALANCE_UPDATE -> {
                // 跳转到首页余额页面
                Intent(this, MainActivity::class.java).apply {
                    putExtra("navigate_to", "balance")
                    addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                }
            }
            else -> {
                // 默认跳转到首页
                Intent(this, MainActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                }
            }
        }
    }

    /**
     * 根据通知类型获取渠道 ID
     */
    private fun getChannelId(type: String): String {
        return when (type) {
            TYPE_TRANSFER_RECEIVED, TYPE_TRANSFER_SENT, TYPE_BALANCE_UPDATE -> CHANNEL_TRANSACTIONS
            TYPE_SECURITY_ALERT -> CHANNEL_SECURITY
            else -> CHANNEL_DEFAULT
        }
    }

    /**
     * 根据通知类型获取优先级
     */
    private fun getNotificationPriority(type: String): Int {
        return when (type) {
            TYPE_TRANSFER_RECEIVED, TYPE_SECURITY_ALERT -> NotificationCompat.PRIORITY_HIGH
            TYPE_TRANSFER_SENT, TYPE_BALANCE_UPDATE -> NotificationCompat.PRIORITY_DEFAULT
            else -> NotificationCompat.PRIORITY_LOW
        }
    }

    /**
     * 生成通知 ID
     */
    private fun generateNotificationId(type: String): Int {
        return when (type) {
            TYPE_TRANSFER_RECEIVED -> (System.currentTimeMillis() % 10000).toInt() + 1000
            TYPE_TRANSFER_SENT -> (System.currentTimeMillis() % 10000).toInt() + 2000
            TYPE_SECURITY_ALERT -> (System.currentTimeMillis() % 10000).toInt() + 3000
            else -> (System.currentTimeMillis() % 10000).toInt()
        }
    }

    /**
     * 创建通知渠道（Android 8.0+）
     */
    private fun createNotificationChannels(notificationManager: NotificationManager) {
        // 交易通知渠道
        val transactionChannel = NotificationChannel(
            CHANNEL_TRANSACTIONS,
            getString(R.string.channel_transactions),
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = getString(R.string.channel_transactions_desc)
            enableVibration(true)
            vibrationPattern = longArrayOf(100, 200, 100, 200)
            enableLights(true)
            lightColor = getColor(R.color.primary)
        }

        // 安全通知渠道
        val securityChannel = NotificationChannel(
            CHANNEL_SECURITY,
            getString(R.string.channel_security),
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = getString(R.string.channel_security_desc)
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 500, 200, 500)
            enableLights(true)
            lightColor = getColor(R.color.error)
        }

        // 默认通知渠道
        val defaultChannel = NotificationChannel(
            CHANNEL_DEFAULT,
            getString(R.string.channel_default),
            NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
            description = getString(R.string.channel_default_desc)
        }

        // 创建渠道
        notificationManager.createNotificationChannel(transactionChannel)
        notificationManager.createNotificationChannel(securityChannel)
        notificationManager.createNotificationChannel(defaultChannel)
    }
}
