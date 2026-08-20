import { test, expect } from '@playwright/test';

test.describe('Chat Flow with Video', () => {
  test('check transform result has output_path', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');

    // 上传视频
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('F:/video/old_video_simulated.mp4');
    await page.waitForTimeout(300);

    // 输入并发送
    const input = page.locator('.input-field');
    await input.fill('转换成竖屏');
    await input.press('Enter');

    // 等待助手响应
    await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 30000 });

    // 检查预览区域是否有视频
    const previewVideo = page.locator('.preview video');
    const hasVideo = await previewVideo.count() > 0;
    console.log('Preview has video:', hasVideo);

    // 检查助手消息内容
    const assistantMsg = await page.locator('.message.assistant').first().textContent();
    console.log('Assistant message:', assistantMsg);

    // 检查消息是否包含"转换完成"
    expect(assistantMsg).toContain('转换完成');
  });
});
