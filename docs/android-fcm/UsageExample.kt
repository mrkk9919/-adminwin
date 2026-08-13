package com.wingbank.mobile

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.wingbank.mobile.fcm.PushManager
import com.wingbank.mobile.ui.login.LoginResult

/**
 * 使用示例
 * 展示如何在各个场景中使用推送功能
 */

// ====== 场景 1：用户登录成功后注册 token ======
class LoginActivity : AppCompatActivity() {

    fun onLoginSuccess(user: User) {
        // 保存用户信息
        // ...

        // 注册推送 token
        PushManager.registerPushToken(user.telegramId)

        // 跳转到首页
        // ...
    }
}

// ====== 场景 2：用户登出时清理 ======
class SettingsActivity : AppCompatActivity() {

    fun onLogout() {
        // 清理推送状态
        PushManager.onLogout()

        // 其他清理工作
        // ...
    }
}

// ====== 场景 3：设置页面开关推送 ======
class PushSettingsActivity : AppCompatActivity() {

    fun onPushToggleChanged(enabled: Boolean) {
        // 保存设置并同步到后端
        PushManager.setPushEnabled(enabled)
    }

    fun checkPushStatus() {
        val isEnabled = PushManager.isPushEnabled()
        // 更新 UI
        // ...
    }
}

// ====== 场景 4：MainActivity 处理通知点击 ======
class MainActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 检查是否从通知点击打开
        handleNotificationIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleNotificationIntent(intent)
    }

    private fun handleNotificationIntent(intent: Intent) {
        val navigateTo = intent.getStringExtra("navigate_to")
        val notificationType = intent.getStringExtra("notification_type")

        when (navigateTo) {
            "balance" -> {
                // 跳转到余额页面
                // navigateToBalance()
            }
            "security" -> {
                // 跳转到安全中心
                // navigateToSecurity()
            }
        }

        when (notificationType) {
            "transfer_received", "transfer_sent" -> {
                // 已经跳转到交易详情页了，这里不需要处理
            }
        }
    }
}

// ====== 场景 5：交易详情页处理 ======
class TransactionDetailActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 从通知获取交易 ID
        val transactionId = intent.getStringExtra("transaction_id")

        if (transactionId != null) {
            // 加载交易详情
            loadTransactionDetail(transactionId)
        } else {
            // 正常进入，从 Intent 获取其他参数
            // ...
        }
    }

    private fun loadTransactionDetail(transactionId: String) {
        // 调用 API 加载交易详情
        // ...
    }
}

// ====== 数据类 ======
data class User(
    val telegramId: Long,
    val username: String,
    val phone: String
    // 其他字段...
)
