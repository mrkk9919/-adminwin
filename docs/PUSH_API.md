# FCM 推送服务 API 文档

## 概述

Wing Bank 推送服务基于 Firebase Cloud Messaging (FCM) 实现，支持向安卓和 iOS 设备发送推送通知。

### 推送流程

```
用户A扫码转账
    ↓
后端处理转账，余额更新
    ↓
查询收款人B的 FCM token
    ↓
调用 FCM 推送服务
    ↓
Firebase 服务器发送推送
    ↓
用户B的手机收到通知
    ↓
点击通知打开 App → 跳转到交易详情页
```

### 架构

```
┌─────────────┐     HTTP      ┌─────────────┐     FCM      ┌─────────────┐
│  Go Bot     │ ────────────→ │ Python 后端 │ ───────────→ │  Firebase   │
│  (tgbot)    │               │  (admin)    │              │   Cloud     │
└─────────────┘               └─────────────┘              │ Messaging   │
                                                           └─────────────┘
                                                                  ↓
                                                           ┌─────────────┐
                                                           │  安卓 App   │
                                                           └─────────────┘
```

---

## 后端 API 接口

### 基础信息

- **Base URL**: `http://your-server:8080`
- **认证方式**: JWT Cookie 或 API Key
- **API Key Header**: `X-API-Key: <token>`
- **Bearer Token Header**: `Authorization: Bearer <token>`
- **Content-Type**: `application/json`

---

### 1. 注册推送 Token

注册或更新用户的 FCM/APNs 设备 token。

**接口地址**: `POST /push/api/register`

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| telegram_id | int | 是 | 用户 Telegram ID |
| fcm_token | string | 否 | FCM 设备 token（安卓） |
| apns_token | string | 否 | APNs 设备 token（iOS） |
| device_type | string | 否 | 设备类型：android / ios |

**请求示例**:

```json
{
  "telegram_id": 123456789,
  "fcm_token": "dU9...fcm_token...XYZ",
  "device_type": "android"
}
```

**响应示例**:

```json
{
  "success": true,
  "message": "Token registered successfully"
}
```

---

### 2. 开关推送通知

开启或关闭用户的推送通知。

**接口地址**: `POST /push/api/toggle`

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| telegram_id | int | 是 | 用户 Telegram ID |
| enabled | bool | 是 | 是否开启推送 |

**请求示例**:

```json
{
  "telegram_id": 123456789,
  "enabled": true
}
```

**响应示例**:

```json
{
  "success": true,
  "message": "Push notifications enabled"
}
```

---

### 3. 发送测试通知

向指定用户发送测试推送通知。

**接口地址**: `POST /push/api/send-test`

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| telegram_id | int | 是 | 用户 Telegram ID |
| title | string | 否 | 通知标题，默认"测试通知" |
| body | string | 否 | 通知内容，默认"这是一条测试推送消息" |

**请求示例**:

```json
{
  "telegram_id": 123456789,
  "title": "测试通知",
  "body": "这是一条测试推送消息"
}
```

**响应示例**:

```json
{
  "success": true,
  "result": {
    "success": 1,
    "failure": 0
  }
}
```

---

### 4. 查询推送状态

查询用户的推送状态和 token 信息。

**接口地址**: `GET /push/api/status?telegram_id=123456789`

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| telegram_id | int | 是 | 用户 Telegram ID |

**响应示例**:

```json
{
  "success": true,
  "data": {
    "telegram_id": 123456789,
    "has_fcm_token": true,
    "has_apns_token": false,
    "push_enabled": true,
    "token_updated_at": "2024-01-15T10:30:00"
  }
}
```

---

### 5. 转账成功通知（付款人）

向付款人发送"转账成功"通知。

**接口地址**: `POST /push/api/transfer-sent`

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| telegram_id | int | 是 | 付款人 Telegram ID |
| amount | string | 是 | 转账金额 |
| currency | string | 是 | 货币类型（USD / KHR） |
| counterparty_name | string | 是 | 收款人姓名 |
| transaction_id | string | 是 | 交易 ID |
| timestamp | string | 否 | ISO8601 时间戳，如 2025-01-01T12:00:00Z |

**请求示例**:

```json
{
  "telegram_id": 123456789,
  "amount": "50.00",
  "currency": "USD",
  "counterparty_name": "张三",
  "transaction_id": "SCAN-abc12345",
  "timestamp": "2025-01-01T12:00:00Z"
}
```

**通知效果**:

> **✅ 转账成功**
> 
> 您已向张三转账 USD 50.00

**响应示例**:

```json
{
  "success": true,
  "result": {
    "success": 1,
    "failure": 0
  }
}
```

---

### 6. 收到转账通知（收款人）

向收款人发送"收到转账"通知。

**接口地址**: `POST /push/api/transfer-received`

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| telegram_id | int | 是 | 收款人 Telegram ID |
| amount | string | 是 | 转账金额 |
| currency | string | 是 | 货币类型（USD / KHR） |
| counterparty_name | string | 是 | 付款人姓名 |
| transaction_id | string | 是 | 交易 ID |
| timestamp | string | 否 | ISO8601 时间戳，如 2025-01-01T12:00:00Z |

**请求示例**:

```json
{
  "telegram_id": 987654321,
  "amount": "50.00",
  "currency": "USD",
  "counterparty_name": "李四",
  "transaction_id": "SCAN-abc12345",
  "timestamp": "2025-01-01T12:00:00Z"
}
```

**通知效果**:

> **✅ 收到转账**
> 
> 您收到 USD 50.00 转账，付款人：李四

**响应示例**:

```json
{
  "success": true,
  "result": {
    "success": 1,
    "failure": 0
  }
}
```

---

## 安卓端集成指南

### 第一步：Firebase 项目设置

1. 访问 [Firebase 控制台](https://console.firebase.google.com/)
2. 创建新项目或选择现有项目
3. 点击"添加应用" → "Android"
4. 填写应用信息：
   - Android 包名：`com.wingbank.mobile`
   - 应用名称：Wing Bank
   - 调试签名证书 SHA-1（可选）
5. 下载 `google-services.json` 文件

### 第二步：添加 FCM 依赖

在项目级 `build.gradle` 中添加：

```gradle
buildscript {
    dependencies {
        classpath 'com.google.gms:google-services:4.4.0'
    }
}
```

在应用级 `build.gradle` 中添加：

```gradle
plugins {
    id 'com.google.gms.google-services'
}

dependencies {
    // FCM
    implementation 'com.google.firebase:firebase-messaging:23.4.0'
    
    // Firebase BOM（推荐）
    implementation platform('com.google.firebase:firebase-bom:32.7.0')
    implementation 'com.google.firebase:firebase-messaging-ktx'
}
```

### 第三步：配置 AndroidManifest.xml

```xml
<manifest>
    <!-- 推送权限 -->
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.INTERNET" />
    
    <application>
        <!-- Firebase Messaging Service -->
        <service
            android:name=".fcm.WingFirebaseMessagingService"
            android:exported="false">
            <intent-filter>
                <action android:name="com.google.firebase.MESSAGING_EVENT" />
            </intent-filter>
        </service>
        
        <!-- 默认通知渠道 -->
        <meta-data
            android:name="com.google.firebase.messaging.default_notification_channel_id"
            android:value="wingbank_default" />
            
        <!-- 默认通知图标 -->
        <meta-data
            android:name="com.google.firebase.messaging.default_notification_icon"
            android:resource="@drawable/ic_notification" />
            
        <!-- 默认通知颜色 -->
        <meta-data
            android:name="com.google.firebase.messaging.default_notification_color"
            android:resource="@color/primary" />
    </application>
</manifest>
```

---

## 完整 Kotlin 代码示例

### 1. Firebase Messaging Service

```kotlin
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

class WingFirebaseMessagingService : FirebaseMessagingService() {

    companion object {
        private const val TAG = "WingFCM"
        
        // 通知渠道
        const val CHANNEL_TRANSACTIONS = "wingbank_transactions"
        const val CHANNEL_DEFAULT = "wingbank_default"
        
        // 通知类型
        const val TYPE_TRANSFER_RECEIVED = "transfer_received"
        const val TYPE_TRANSFER_SENT = "transfer_sent"
        const val TYPE_BALANCE_UPDATE = "balance_update"
        const val TYPE_SECURITY_ALERT = "security_alert"
    }

    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        Log.d(TAG, "From: ${remoteMessage.from}")

        // 检查是否包含通知负载
        remoteMessage.notification?.let { notification ->
            Log.d(TAG, "Notification Title: ${notification.title}")
            Log.d(TAG, "Notification Body: ${notification.body}")
            
            // 解析数据负载
            val type = remoteMessage.data["type"] ?: "default"
            val transactionId = remoteMessage.data["transaction_id"]
            
            // 显示通知
            sendNotification(
                title = notification.title ?: "Wing Bank",
                body = notification.body ?: "",
                type = type,
                transactionId = transactionId
            )
        }
    }

    override fun onNewToken(token: String) {
        Log.d(TAG, "Refreshed token: $token")
        
        // 将新 token 发送到后端
        sendRegistrationToServer(token)
    }

    private fun sendNotification(
        title: String,
        body: String,
        type: String,
        transactionId: String?
    ) {
        // 创建通知点击意图
        val intent = when (type) {
            TYPE_TRANSFER_RECEIVED, TYPE_TRANSFER_SENT -> {
                // 跳转到交易详情页
                Intent(this, TransactionDetailActivity::class.java).apply {
                    putExtra("transaction_id", transactionId)
                    addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
                }
            }
            else -> {
                // 默认跳转到首页
                Intent(this, MainActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
                }
            }
        }

        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_IMMUTABLE
        )

        // 根据类型选择通知渠道
        val channelId = when (type) {
            TYPE_TRANSFER_RECEIVED, TYPE_TRANSFER_SENT -> CHANNEL_TRANSACTIONS
            else -> CHANNEL_DEFAULT
        }

        val defaultSoundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
        
        val notificationBuilder = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .setSound(defaultSoundUri)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_HIGH)

        val notificationManager = 
            getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        // Android 8.0+ 需要创建通知渠道
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            createNotificationChannels(notificationManager)
        }

        // 使用唯一 ID 显示通知
        val notificationId = System.currentTimeMillis().toInt()
        notificationManager.notify(notificationId, notificationBuilder.build())
    }

    private fun createNotificationChannels(notificationManager: NotificationManager) {
        // 交易通知渠道
        val transactionChannel = NotificationChannel(
            CHANNEL_TRANSACTIONS,
            "交易通知",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "转账、收款等交易相关通知"
            enableVibration(true)
            vibrationPattern = longArrayOf(100, 200, 100, 200)
        }
        
        // 默认通知渠道
        val defaultChannel = NotificationChannel(
            CHANNEL_DEFAULT,
            "其他通知",
            NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
            description = "其他系统通知"
        }

        notificationManager.createNotificationChannel(transactionChannel)
        notificationManager.createNotificationChannel(defaultChannel)
    }

    private fun sendRegistrationToServer(token: String) {
        // 在这里实现将 token 发送到后端的逻辑
        // 调用 POST /push/api/register 接口
        Log.d(TAG, "Sending token to server: $token")
        
        // 示例：使用 Retrofit 或 OkHttp 发送
        // apiService.registerPushToken(
        //     telegramId = userId,
        //     fcmToken = token,
        //     deviceType = "android"
        // )
    }
}
```

### 2. 注册 Token 工具类

```kotlin
package com.wingbank.mobile.fcm

import android.util.Log
import com.google.firebase.messaging.Firebase
import com.google.firebase.messaging.FirebaseMessaging

object PushManager {

    private const val TAG = "PushManager"

    /**
     * 获取 FCM token 并注册到后端
     */
    fun registerPushToken(telegramId: Long) {
        FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
            if (!task.isSuccessful) {
                Log.w(TAG, "Fetching FCM registration token failed", task.exception)
                return@addOnCompleteListener
            }

            // 获取新 token
            val token = task.result
            Log.d(TAG, "FCM Token: $token")

            // 注册到后端
            registerToServer(telegramId, token)
        }
    }

    /**
     * 订阅主题（用于广播通知）
     */
    fun subscribeToTopic(topic: String) {
        FirebaseMessaging.getInstance().subscribeToTopic(topic)
            .addOnCompleteListener { task ->
                val msg = if (task.isSuccessful) "Subscribed" else "Subscribe failed"
                Log.d(TAG, "$msg to topic: $topic")
            }
    }

    /**
     * 取消订阅主题
     */
    fun unsubscribeFromTopic(topic: String) {
        FirebaseMessaging.getInstance().unsubscribeFromTopic(topic)
            .addOnCompleteListener { task ->
                val msg = if (task.isSuccessful) "Unsubscribed" else "Unsubscribe failed"
                Log.d(TAG, "$msg from topic: $topic")
            }
    }

    private fun registerToServer(telegramId: Long, token: String) {
        // 实现你的 API 调用逻辑
        // 示例：
        /*
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val response = apiService.registerPushToken(
                    RegisterPushTokenRequest(
                        telegramId = telegramId,
                        fcmToken = token,
                        deviceType = "android"
                    )
                )
                Log.d(TAG, "Token registered successfully: ${response.success}")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to register token", e)
            }
        }
        */
    }
}
```

### 3. 登录时调用

```kotlin
// 在用户登录成功后调用
PushManager.registerPushToken(user.telegramId)
```

---

## 通知点击跳转处理

### 交易详情页 Activity

```kotlin
package com.wingbank.mobile.ui.transaction

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.wingbank.mobile.databinding.ActivityTransactionDetailBinding

class TransactionDetailActivity : AppCompatActivity() {

    private lateinit var binding: ActivityTransactionDetailBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityTransactionDetailBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // 从通知获取交易 ID
        val transactionId = intent.getStringExtra("transaction_id")
        
        if (transactionId != null) {
            // 加载交易详情
            loadTransactionDetail(transactionId)
        } else {
            finish()
        }
    }

    private fun loadTransactionDetail(transactionId: String) {
        // 实现加载交易详情的逻辑
        // 调用 API 获取交易信息并显示
    }
}
```

---

## Go 端使用示例

### 初始化推送服务

```go
import "tgbot/services"

// 在 main.go 中初始化
services.InitPushService(cfg.PushBaseURL)
```

### 发送转账成功通知

```go
// 给付款人发通知
go func() {
    if services.GlobalPush != nil {
        err := services.GlobalPush.SendTransferSent(
            userID,           // 付款人 Telegram ID
            amount,           // 金额
            currency,         // 货币
            receiverName,     // 收款人姓名
            txID,             // 交易 ID
        )
        if err != nil {
            log.Printf("Failed to send push: %v", err)
        }
    }
}()
```

### 发送收到转账通知

```go
// 给收款人发通知
go func() {
    if services.GlobalPush != nil {
        err := services.GlobalPush.SendTransferReceived(
            receiverID,       // 收款人 Telegram ID
            amount,           // 金额
            currency,         // 货币
            senderName,       // 付款人姓名
            txID,             // 交易 ID
        )
        if err != nil {
            log.Printf("Failed to send push: %v", err)
        }
    }
}()
```

---

## 配置说明

### 环境变量

在 `admin/.env` 中配置：

```env
# Firebase Cloud Messaging 服务器密钥
FCM_SERVER_KEY=your_fcm_server_key

# 可选：APNs 认证（iOS）
# APNS_KEY_ID=your_key_id
# APNS_TEAM_ID=your_team_id
# APNS_BUNDLE_ID=com.wingbank.mobile
```

在 `tgbot` 的环境变量中配置：

```env
# Python 后端地址，用于调用推送 API
PUSH_BASE_URL=http://localhost:8080
```

---

## 常见问题解答

### Q1: 收不到推送通知怎么办？

**检查清单：**
1. ✅ 确认设备已联网
2. ✅ 确认 App 已获取通知权限
3. ✅ 确认 FCM token 已正确注册到后端
4. ✅ 确认 FCM_SERVER_KEY 配置正确
5. ✅ 检查 Firebase 控制台的"发送测试消息"是否能收到
6. ✅ 检查后端日志，看是否有推送错误

### Q2: token 会过期吗？

FCM token 可能在以下情况失效：
- 应用删除数据
- 用户清除应用数据
- 应用重新安装
- Firebase 主动刷新 token

**处理方式：**
- 每次启动 App 时检查并更新 token
- 实现 `onNewToken()` 回调处理 token 刷新
- 后端记录 token 更新时间，定期清理过期 token

### Q3: 如何批量发送推送？

使用 `send_multicast_push()` 函数，最多支持一次发送 500 个 token。

### Q4: 推送通知可以带图片吗？

可以，在通知中添加 `image` 字段即可。但需要注意图片大小限制（通常 1MB 以内）。

### Q5: 如何处理离线消息？

FCM 会自动缓存离线消息，设备上线后会自动送达。可以设置 `time_to_live` 参数控制消息有效期（最长 4 周）。

### Q6: iOS 推送怎么集成？

iOS 使用 APNs（Apple Push Notification service），需要：
1. 在 Apple 开发者账号创建 APNs 证书
2. 在 Firebase 控制台上传 APNs 证书
3. 后端使用 APNs token 发送推送

---

## 测试方法

### 方法 1：Firebase 控制台测试

1. 打开 Firebase 控制台
2. 进入 "Messaging" → "发送第一条消息"
3. 输入通知标题和内容
4. 选择"单个设备"，填入 FCM token
5. 点击"测试"

### 方法 2：后端 API 测试

```bash
curl -X POST http://localhost:8080/push/api/send-test \
  -H "Content-Type: application/json" \
  -d '{
    "telegram_id": 123456789,
    "title": "测试通知",
    "body": "这是一条测试推送消息"
  }'
```

### 方法 3：管理后台测试

访问管理后台 `/push` 页面，选择用户并发送测试通知。

---

## 管理后台

### 访问地址

`http://your-server:8080/push`

### 功能

- 查看已注册推送的用户列表
- 查看用户的推送状态
- 手动发送测试通知
- 开启/关闭用户的推送权限

---

## 错误码

| HTTP 状态码 | 说明 |
|------------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 用户不存在 |
| 403 | 权限不足 |
| 500 | 服务器内部错误 |

---

## 更新日志

### v1.0.0 (2024-01-15)
- 初始版本
- 支持 FCM 推送
- 支持转账通知
- 支持管理后台
