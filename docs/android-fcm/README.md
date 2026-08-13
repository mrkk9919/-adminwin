# Wing Bank 安卓端 FCM 集成指南

## 📁 文件结构

```
android-fcm/
├── fcm/
│   ├── WingFirebaseMessagingService.kt  # FCM 消息接收服务
│   └── PushManager.kt                   # 推送管理工具类
├── api/
│   ├── ApiService.kt                    # API 接口定义
│   └── RetrofitClient.kt                # Retrofit 客户端
├── utils/
│   └── NotificationHelper.kt            # 通知工具类
├── config/
│   ├── build.gradle_app.txt             # 应用级 build.gradle
│   ├── build.gradle_project.txt         # 项目级 build.gradle
│   ├── AndroidManifest.xml              # 清单文件配置
│   └── strings.xml                      # 字符串资源
├── WingBankApplication.kt               # Application 类
├── UsageExample.kt                      # 使用示例
└── README.md                            # 本文档
```

---

## 🚀 集成步骤

### 第一步：Firebase 项目设置

1. **创建 Firebase 项目**
   - 访问 [Firebase 控制台](https://console.firebase.google.com/)
   - 点击"添加项目"，输入项目名称：Wing Bank
   - 等待项目创建完成

2. **添加 Android 应用**
   - 点击"添加应用" → "Android"
   - 填写 Android 包名：`com.wingbank.mobile`
   - 应用名称：Wing Bank
   - （可选）填写调试签名证书 SHA-1
   - 点击"注册应用"

3. **下载配置文件**
   - 下载 `google-services.json` 文件
   - 将文件放到 Android 项目的 `app/` 目录下

---

### 第二步：添加依赖

1. **项目级 build.gradle**
   - 参考 `config/build.gradle_project.txt`
   - 添加 Google services 插件：
     ```gradle
     classpath 'com.google.gms:google-services:4.4.0'
     ```

2. **应用级 build.gradle**
   - 参考 `config/build.gradle_app.txt`
   - 添加插件：
     ```gradle
     id 'com.google.gms.google-services'
     ```
   - 添加依赖：
     ```gradle
     implementation platform('com.google.firebase:firebase-bom:32.7.0')
     implementation 'com.google.firebase:firebase-messaging-ktx'
     ```

---

### 第三步：配置 AndroidManifest.xml

参考 `config/AndroidManifest.xml`，添加：

1. **权限**
   ```xml
   <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
   <uses-permission android:name="android.permission.INTERNET" />
   <uses-permission android:name="android.permission.WAKE_LOCK" />
   <uses-permission android:name="android.permission.VIBRATE" />
   ```

2. **Service**
   ```xml
   <service
       android:name=".fcm.WingFirebaseMessagingService"
       android:exported="false">
       <intent-filter>
           <action android:name="com.google.firebase.MESSAGING_EVENT" />
       </intent-filter>
   </service>
   ```

3. **默认通知配置**
   ```xml
   <meta-data
       android:name="com.google.firebase.messaging.default_notification_channel_id"
       android:value="wingbank_default" />
   ```

---

### 第四步：复制代码文件

将以下文件复制到你的项目对应目录：

| 源文件 | 目标目录 |
|--------|----------|
| `fcm/WingFirebaseMessagingService.kt` | `app/src/main/java/com/wingbank/mobile/fcm/` |
| `fcm/PushManager.kt` | `app/src/main/java/com/wingbank/mobile/fcm/` |
| `api/ApiService.kt` | `app/src/main/java/com/wingbank/mobile/api/` |
| `api/RetrofitClient.kt` | `app/src/main/java/com/wingbank/mobile/api/` |
| `utils/NotificationHelper.kt` | `app/src/main/java/com/wingbank/mobile/utils/` |
| `WingBankApplication.kt` | `app/src/main/java/com/wingbank/mobile/` |

---

### 第五步：配置字符串资源

参考 `config/strings.xml`，添加通知渠道和推送文案。

---

### 第六步：修改 RetrofitClient.kt

修改 `RetrofitClient.kt` 中的 `BASE_URL` 为你的后端地址：

```kotlin
private const val BASE_URL = "https://your-server.com/"
```

---

### 第七步：在登录/注册时调用

在用户登录成功后，调用：

```kotlin
PushManager.registerPushToken(user.telegramId)
```

参考 `UsageExample.kt` 中的 `LoginActivity` 示例。

---

## 📱 通知类型说明

| 类型 | 通知渠道 | 优先级 | 点击跳转 |
|------|----------|--------|----------|
| `transfer_received` | 交易通知 | 高 | 交易详情页 |
| `transfer_sent` | 交易通知 | 中 | 交易详情页 |
| `balance_update` | 交易通知 | 中 | 首页余额页 |
| `security_alert` | 安全提醒 | 高 | 安全中心 |
| `test` | 其他通知 | 低 | 首页 |

---

## 🔧 常见问题

### Q1: 收不到推送怎么办？

**检查清单：**
1. ✅ 确认设备已联网
2. ✅ 确认 App 已获取通知权限（Android 13+）
3. ✅ 确认 `google-services.json` 配置正确
4. ✅ 确认 FCM token 已正确注册到后端
5. ✅ 在 Firebase 控制台发送测试消息，看是否能收到
6. ✅ 检查后端日志，看是否有推送错误

### Q2: token 会过期吗？

FCM token 可能在以下情况失效：
- 应用删除数据
- 用户清除应用数据
- 应用重新安装
- Firebase 主动刷新 token

**处理方式：**
- 每次启动 App 时调用 `PushManager.checkAndRefreshToken()`
- `WingFirebaseMessagingService.onNewToken()` 会自动处理 token 刷新

### Q3: 如何在后台接收推送？

- 当 App 在后台时，FCM 会自动显示通知
- 当 App 在前台时，`onMessageReceived()` 会被调用，由我们自己显示通知
- 数据负载（data）在两种情况下都会传递

### Q4: 通知点击跳转不生效？

检查：
1. `PendingIntent` 的 flags 是否正确
2. 目标 Activity 是否在 `AndroidManifest.xml` 中声明
3. Intent 的 extra 是否正确传递

### Q5: 如何测试推送？

**方法 1：Firebase 控制台**
- 打开 Firebase 控制台 → Messaging → 发送第一条消息
- 输入标题和内容
- 选择"单个设备"，填入 FCM token
- 点击测试

**方法 2：后端 API**
```bash
curl -X POST https://your-server.com/push/api/send-test \
  -H "Content-Type: application/json" \
  -d '{
    "telegram_id": 123456789,
    "title": "测试通知",
    "body": "这是一条测试推送消息"
  }'
```

**方法 3：管理后台**
- 访问管理后台 `/push` 页面
- 选择用户，点击"发送测试通知"

---

## 📊 推送数据格式

### 转账成功通知（付款人）

```json
{
  "notification": {
    "title": "转账成功",
    "body": "您已向张三转账 USD 50.00"
  },
  "data": {
    "type": "transfer_sent",
    "transaction_id": "SCAN-abc12345",
    "amount": "50.00",
    "currency": "USD",
    "receiver_name": "张三"
  }
}
```

### 收到转账通知（收款人）

```json
{
  "notification": {
    "title": "收到转账",
    "body": "您收到 USD 50.00 转账，付款人：李四"
  },
  "data": {
    "type": "transfer_received",
    "transaction_id": "SCAN-abc12345",
    "amount": "50.00",
    "currency": "USD",
    "sender_name": "李四"
  }
}
```

---

## 🔔 通知渠道说明

### 1. 交易通知 (`wingbank_transactions`)
- **重要性**：高
- **振动**：是
- **指示灯**：是（蓝色）
- **包含**：转账、收款、余额变动

### 2. 安全提醒 (`wingbank_security`)
- **重要性**：高
- **振动**：是（强振动）
- **指示灯**：是（红色）
- **包含**：登录提醒、异常操作、安全验证

### 3. 活动优惠 (`wingbank_promotions`)
- **重要性**：低
- **振动**：否
- **包含**：促销活动、优惠信息

### 4. 其他通知 (`wingbank_default`)
- **重要性**：默认
- **包含**：其他系统通知

---

## ✅ 集成检查清单

- [ ] Firebase 项目已创建
- [ ] `google-services.json` 已放入 `app/` 目录
- [ ] 项目级 build.gradle 已添加插件
- [ ] 应用级 build.gradle 已添加依赖
- [ ] AndroidManifest.xml 已配置权限和 Service
- [ ] 所有 Kotlin 文件已复制到项目
- [ ] `RetrofitClient.BASE_URL` 已修改为正确地址
- [ ] 字符串资源已添加
- [ ] Application 类已配置
- [ ] 登录成功后调用 `PushManager.registerPushToken()`
- [ ] 登出时调用 `PushManager.onLogout()`
- [ ] 已在 Firebase 控制台测试推送
- [ ] 已通过后端 API 测试推送

---

## 📚 相关文档

- [Firebase Cloud Messaging 官方文档](https://firebase.google.com/docs/cloud-messaging)
- [FCM Android 集成指南](https://firebase.google.com/docs/cloud-messaging/android/client)
- [通知渠道最佳实践](https://developer.android.com/develop/ui/views/notifications/channels)
