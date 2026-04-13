<template>
  <div class="view-stack">
    <section class="hero-panel">
      <p class="hero-kicker">项目总览</p>
      <h3>平台已进入可交付候选阶段</h3>
      <p>
        当前版本已覆盖用户登录、分组权限、文档上传与任务追踪、聊天问答、模型提供商管理、
        监控与发布检查等主流程，可继续按验收清单推进最终交付。
      </p>
    </section>

    <section class="card-grid">
      <FeatureCard
        label="功能"
        title="核心链路已贯通"
        description="登录、聊天、文档、管理、设置等页面已接入实际接口并可联调。"
      />
      <FeatureCard
        label="质量"
        title="验收与回归已接入"
        description="后端测试、前端构建与浏览器 Smoke 流程已纳入常规验收。"
      />
      <FeatureCard
        label="运维"
        title="部署与监控已具备基础能力"
        description="Compose、Prometheus、Grafana 和发布检查脚本已完成基础收口。"
      />
    </section>
  </div>
</template>

<script setup>
import FeatureCard from "../components/FeatureCard.vue";
</script>
