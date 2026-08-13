package com.wingbank.mobile.fcm

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import com.google.firebase.messaging.FirebaseMessaging
import com.wingbank.mobile.api.ApiService
import com.wingbank.mobile.api.RetrofitClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * PushManager - 推送管理工具类
 * 负责 FCM token 的获取、注册、更新等
 */
object PushManager {

    private const val TAG = "PushManager"
    private const val PREFS_NAME = "wingbank_push"
    private const val KEY_FCM_TOKEN = "fcm_token"
    private const val KEY_TOKEN_SENT = "token_sent"
    private const val KEY_PUSH_ENABLED = "push_enabled"

    private lateinit var prefs: SharedPreferences
    private var apiService: ApiService? = null
    private var currentUserId: Long = -1

    /**
     * 初始化 PushManager
     * 在 Application 或 MainActivity 中调用
     */
    fun init(context: Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        apiService = RetrofitClient.apiService
        Log.d(TAG, "PushManager initialized")
    }

    /**
     * 设置当前用户 ID
     * 用户登录后调用
     */
    fun setUserId(userId: Long) {
        currentUserId = userId
        Log.d(TAG, "Set user ID: $userId")
    }

    /**
     * 注册推送 token
     * 用户登录成功后调用
     */
    fun registerPushToken(userId: Long) {
        currentUserId = userId

        FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
            if (!task.isSuccessful) {
                Log.w(TAG, "Fetching FCM registration token failed", task.exception)
                return@addOnCompleteListener
            }

            // 获取新 token
            val token = task.result
            Log.d(TAG, "FCM Token: ${token.take(20)}...")

            // 保存到本地
            saveToken(token)

            // 注册到后端
            sendTokenToServer(token)
        }
    }

    /**
     * 发送 token 到后端服务器
     */
    fun sendTokenToServer(token: String) {
        if (currentUserId <= 0) {
            Log.w(TAG, "User ID not set, skipping token upload")
            return
        }

        val service = apiService ?: run {
            Log.w(TAG, "API service not initialized")
            return
        }

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val response = service.registerPushToken(
                    telegramId = currentUserId,
                    fcmToken = token,
                    deviceType = "android"
                )

                if (response.success) {
                    Log.d(TAG, "Token registered successfully")
                    setTokenSent(true)
                } else {
                    Log.e(TAG, "Token registration failed: ${response.message}")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to register token", e)
            }
        }
    }

    /**
     * 检查并更新 token
     * App 启动时调用，确保 token 是最新的
     */
    fun checkAndRefreshToken() {
        FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
            if (task.isSuccessful) {
                val token = task.result
                val savedToken = getToken()

                if (token != savedToken) {
                    Log.d(TAG, "Token changed, updating...")
                    saveToken(token)
                    if (currentUserId > 0) {
                        sendTokenToServer(token)
                    }
                } else {
                    Log.d(TAG, "Token is up to date")
                }
            }
        }
    }

    /**
     * 开启/关闭推送
     */
    fun setPushEnabled(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_PUSH_ENABLED, enabled).apply()

        if (currentUserId > 0) {
            val service = apiService ?: return
            CoroutineScope(Dispatchers.IO).launch {
                try {
                    service.togglePush(currentUserId, enabled)
                    Log.d(TAG, "Push ${if (enabled) "enabled" else "disabled"}")
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to toggle push", e)
                }
            }
        }
    }

    /**
     * 检查推送是否开启
     */
    fun isPushEnabled(): Boolean {
        return prefs.getBoolean(KEY_PUSH_ENABLED, true)
    }

    /**
     * 订阅主题
     * 用于广播通知，如系统公告等
     */
    fun subscribeToTopic(topic: String) {
        FirebaseMessaging.getInstance().subscribeToTopic(topic)
            .addOnCompleteListener { task ->
                if (task.isSuccessful) {
                    Log.d(TAG, "Subscribed to topic: $topic")
                } else {
                    Log.w(TAG, "Failed to subscribe to topic: $topic", task.exception)
                }
            }
    }

    /**
     * 取消订阅主题
     */
    fun unsubscribeFromTopic(topic: String) {
        FirebaseMessaging.getInstance().unsubscribeFromTopic(topic)
            .addOnCompleteListener { task ->
                if (task.isSuccessful) {
                    Log.d(TAG, "Unsubscribed from topic: $topic")
                } else {
                    Log.w(TAG, "Failed to unsubscribe from topic: $topic", task.exception)
                }
            }
    }

    /**
     * 用户登出时调用
     * 取消订阅，清除本地状态
     */
    fun onLogout() {
        // 取消所有主题订阅（如果有的话）
        // unsubscribeFromTopic("all_users")

        // 清除本地状态
        currentUserId = -1
        setTokenSent(false)

        Log.d(TAG, "Push manager cleaned up on logout")
    }

    // --- 本地存储 ---

    private fun saveToken(token: String) {
        prefs.edit().putString(KEY_FCM_TOKEN, token).apply()
    }

    fun getToken(): String? {
        return prefs.getString(KEY_FCM_TOKEN, null)
    }

    private fun setTokenSent(sent: Boolean) {
        prefs.edit().putBoolean(KEY_TOKEN_SENT, sent).apply()
    }

    fun isTokenSent(): Boolean {
        return prefs.getBoolean(KEY_TOKEN_SENT, false)
    }
}
