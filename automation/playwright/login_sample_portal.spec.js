const { test, expect } = require('@playwright/test');

/**
 * Playwright automation script for healthcare portal login
 * This script demonstrates automated login flow with placeholder credentials
 */
test.describe('Healthcare Portal Login', () => {
  
  test('should successfully login to sample healthcare portal', async ({ page }) => {
    console.log('Starting healthcare portal login test');
    
    // Step 1: Navigate to sample healthcare portal login page
    const portalUrl = 'https://sample-healthcare-portal.example.com/login';
    console.log(`Navigating to portal: ${portalUrl}`);
    await page.goto(portalUrl);
    
    // Step 2: Fill username field with placeholder variable
    const username = process.env.PORTAL_USERNAME || 'testuser@healthcare.com';
    console.log(`Filling username field with: ${username}`);
    await page.fill('[data-testid="username"]', username);
    
    // Alternative selectors for username field
    // await page.fill('input[name="username"]', username);
    // await page.fill('#username', username);
    
    // Step 3: Fill password field with placeholder variable
    const password = process.env.PORTAL_PASSWORD || 'testpassword123';
    console.log('Filling password field');
    await page.fill('[data-testid="password"]', password);
    
    // Alternative selectors for password field
    // await page.fill('input[name="password"]', password);
    // await page.fill('#password', password);
    
    // Step 4: Click login button
    console.log('Clicking login button');
    await page.click('[data-testid="login-button"]');
    
    // Alternative selectors for login button
    // await page.click('button[type="submit"]');
    // await page.click('#login-btn');
    
    // Wait for navigation after login
    await page.waitForLoadState('networkidle');
    
    // Step 5: Confirm login success by checking for dashboard element
    console.log('Verifying login success by checking dashboard');
    
    // Wait for dashboard element to be visible
    await page.waitForSelector('[data-testid="dashboard"]', { timeout: 10000 });
    
    // Verify dashboard is visible
    const dashboardElement = page.locator('[data-testid="dashboard"]');
    await expect(dashboardElement).toBeVisible();
    
    // Additional verification options
    // await expect(page).toHaveURL(/.*dashboard.*/); // URL contains 'dashboard'
    // await expect(page.locator('.welcome-message')).toBeVisible();
    // await expect(page.locator('h1')).toContainText('Dashboard');
    
    console.log('Login test completed successfully');
    
    // Log current page URL for verification
    const currentUrl = page.url();
    console.log(`Current page URL after login: ${currentUrl}`);
    
    // Take a screenshot for debugging purposes (optional)
    await page.screenshot({ path: 'login-success-screenshot.png' });
    console.log('Screenshot saved: login-success-screenshot.png');
  });
  
  test('should handle login failure gracefully', async ({ page }) => {
    console.log('Testing login failure scenario');
    
    const portalUrl = 'https://sample-healthcare-portal.example.com/login';
    await page.goto(portalUrl);
    
    // Use invalid credentials
    await page.fill('[data-testid="username"]', 'invalid@example.com');
    await page.fill('[data-testid="password"]', 'wrongpassword');
    await page.click('[data-testid="login-button"]');
    
    // Check for error message
    const errorMessage = page.locator('[data-testid="error-message"]');
    await expect(errorMessage).toBeVisible();
    
    console.log('Login failure test completed - error message displayed');
  });
});

/**
 * Setup and teardown hooks
 */
test.beforeEach(async ({ page }) => {
  console.log('Setting up test environment');
  // Set viewport size
  await page.setViewportSize({ width: 1280, height: 720 });
  
  // Set timeout for all tests
  test.setTimeout(30000);
});

test.afterEach(async ({ page }) => {
  console.log('Cleaning up test environment');
  // Close any open dialogs or popups
  await page.close();
});
