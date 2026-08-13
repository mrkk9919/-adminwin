package com.wingbank.mobile.api

import retrofit2.Call
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

/**
 * Wing Bank API Service
 * 推送相关的 API 接口
 */
interface ApiService {

    /**
     * 注册推送 Token
     * POST /push/api/register
     */
    @FormUrlEncoded
    @POST("push/api/register")
    fun registerPushToken(
        @Field("telegram_id") telegramId: Long,
        @Field("fcm_token") fcmToken: String,
        @Field("device_type") deviceType: String = "android"
    ): Call<BaseResponse>

    /**
     * 开关推送通知
     * POST /push/api/toggle
     */
    @FormUrlEncoded
    @POST("push/api/toggle")
    fun togglePush(
        @Field("telegram_id") telegramId: Long,
        @Field("enabled") enabled: Boolean
    ): Call<BaseResponse>

    /**
     * 发送测试通知
     * POST /push/api/send-test
     */
    @FormUrlEncoded
    @POST("push/api/send-test")
    fun sendTestNotification(
        @Field("telegram_id") telegramId: Long,
        @Field("title") title: String = "测试通知",
        @Field("body") body: String = "这是一条测试推送消息"
    ): Call<BaseResponse>

    /**
     * 查询推送状态
     * GET /push/api/status
     */
    @GET("push/api/status")
    fun getPushStatus(
        @Query("telegram_id") telegramId: Long
    ): Call<PushStatusResponse>
}

/**
 * 基础响应
 */
data class BaseResponse(
    val success: Boolean,
    val message: String? = null,
    val error: String? = null
)

/**
 * 推送状态响应
 */
data class PushStatusResponse(
    val success: Boolean,
    val data: PushStatusData?
)

data class PushStatusData(
    val telegram_id: Long,
    val has_fcm_token: Boolean,
    val has_apns_token: Boolean,
    val push_enabled: Boolean,
    val token_updated_at: String?
)
