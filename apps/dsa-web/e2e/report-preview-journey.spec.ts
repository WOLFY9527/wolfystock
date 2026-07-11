import { expect, test, type Page } from '@playwright/test';

async function expectNoDocumentOverflow(page: Page) {
  const overflow = await page.evaluate(() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth));
  expect(overflow).toBeLessThanOrEqual(1);
}

test.describe('report preview journey', () => {
  test('keeps full-report drawer evidence, export, Escape, and mobile contracts intact', async ({ page, context }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/__preview/full-report');
    await page.waitForLoadState('domcontentloaded');

    const openChineseReport = page.getByRole('button', { name: '打开中文完整报告' });
    await expect(openChineseReport).toBeVisible({ timeout: 15_000 });
    await openChineseReport.click();

    const reportShell = page.getByTestId('full-report-document-shell');
    await expect(reportShell).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('report-observation-time-strip')).toContainText('观察时间');
    await expect(page.getByTestId('report-observation-time-strip')).toContainText('2026-03-28 09:35:00 EDT');
    await expect(page.getByTestId('report-observation-time-strip')).toContainText('报告生成时间');
    await expect(page.getByTestId('report-observation-time-strip')).toContainText('2026-03-28 21:35:00 CST');
    await expect(page.getByTestId('report-export-controls')).toContainText('导出内容保留当前研究证据，不新增投资建议。');

    await page.getByTestId('report-technical-evidence-details').locator('summary').click();
    await expect(page.getByTestId('report-technical-details-renderer')).toContainText('一、结论摘要', { timeout: 15_000 });
    await expect(page.getByRole('columnheader', { name: '字段' })).toBeVisible();
    await expectNoDocumentOverflow(page);

    const origin = new URL(page.url()).origin;
    await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin });
    await page.getByRole('button', { name: '复制报告' }).click();
    await expect(page.getByRole('status')).toContainText('报告已复制。');

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: '下载 Markdown' }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe('WolfyStock_英伟达_NVDA_20260328.md');
    await expect(page.getByRole('status')).toContainText('Markdown 下载已开始。');

    const popupPromise = page.waitForEvent('popup');
    await page.getByRole('button', { name: '打印 / PDF' }).click();
    const printPage = await popupPromise;
    await expect(printPage.locator('#wolfystock-preview-print-report')).toContainText('本报告用于研究讨论，不构成投资建议。');
    await printPage.close();
    await expect(page.getByRole('status')).toContainText('打印 / PDF 流程已打开。');

    await page.keyboard.press('Escape');
    await expect(reportShell).toBeHidden({ timeout: 15_000 });
    await expect(openChineseReport).toBeFocused();
  });
});
