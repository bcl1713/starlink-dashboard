import { test, expect } from '@playwright/test';

test.describe('Mission Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // Mock initial empty mission list
    await page.route('http://localhost:8000/api/v2/missions', async (route) => {
      const method = route.request().method();
      if (method === 'GET') {
        await route.fulfill({ json: [] });
      } else {
        await route.continue();
      }
    });

    // Mock route list (for adding legs later)
    await page.route('http://localhost:8000/api/routes', async (route) => {
      await route.fulfill({
        json: {
          routes: [{ id: 'route-1', name: 'Test Route' }],
          total: 1
        }
      });
    });
  });

  test('should create a new mission', async ({ page }) => {
    // 1. Navigate to home
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: 'Missions' })).toBeVisible();
    await expect(page.getByText('No missions yet. Create your first mission to get started.')).toBeVisible();

    // 2. Mock Create Mission API
    let createdMission: any = null;
    await page.route('http://localhost:8000/api/v2/missions', async (route) => {
      if (route.request().method() === 'POST') {
        const data = route.request().postDataJSON();
        createdMission = {
          ...data,
          id: 'new-mission',
          legs: []
        };
        await route.fulfill({ json: createdMission });
      } else if (route.request().method() === 'GET') {
        // Return the created mission if it exists, otherwise empty
        await route.fulfill({ json: createdMission ? [createdMission] : [] });
      } else {
        await route.continue();
      }
    });

    // 3. Open Create Dialog
    await page.getByRole('button', { name: 'Create New Mission' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Create New Mission' })).toBeVisible();

    // 4. Fill Form
    await page.getByLabel('Mission Name').fill('New Mission');
    await page.getByLabel('Description').fill('Test Description');

    // 5. Submit
    await page.getByRole('button', { name: 'Create Mission' }).click();

    // 6. Verify Dialog Closes and Mission Appears
    await expect(page.getByRole('dialog')).not.toBeVisible();
    await expect(page.getByText('New Mission', { exact: true })).toBeVisible();
    await expect(page.getByText('Test Description')).toBeVisible();
  });

  test('should manage legs', async ({ page }) => {
    const mission = {
      id: 'test-mission',
      name: 'Test Mission',
      description: 'Test Desc',
      legs: []
    };

    // Mock initial state with one mission
    await page.route('http://localhost:8000/api/v2/missions', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ json: [mission] });
      } else {
        await route.continue();
      }
    });

    // Mock mission detail
    await page.route('http://localhost:8000/api/v2/missions/test-mission', async (route) => {
      await route.fulfill({ json: mission });
    });

    // Mock Add Leg API
    await page.route('http://localhost:8000/api/v2/missions/test-mission/legs', async (route) => {
        const data = route.request().postDataJSON();
        // Return success
        await route.fulfill({ json: { ...data, id: 'leg-1' } });
    });

    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.getByText('Test Mission').click();

    // Verify Detail Page
    await expect(page.getByRole('heading', { name: 'Test Mission' })).toBeVisible();
    await expect(page.getByText('No legs configured')).toBeVisible();

    // Add Leg
    await page.getByRole('button', { name: 'Add Leg' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    
    await page.getByLabel('Leg Name').fill('Leg 1');
    
    // Select Route (this might be tricky depending on Radix UI Select)
    // We mock the routes so "Select Existing" should be active.
    // Radix Select Trigger
    await page.getByRole('combobox').click();
    await expect(page.getByRole('option', { name: 'Test Route' })).toBeVisible();
    await page.getByRole('option', { name: 'Test Route' }).click();

    await page.getByRole('button', { name: 'Add Leg' }).click();

    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('should handle export/import', async ({ page }) => {
     const mission = {
      id: 'test-mission',
      name: 'Test Mission',
      description: 'Test Desc',
      legs: []
    };

    await page.route('http://localhost:8000/api/v2/missions', async (route) => {
        await route.fulfill({ json: [mission] });
    });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Check Export
    await expect(page.getByRole('button', { name: 'Export' })).toBeVisible();
    await page.getByRole('button', { name: 'Export' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Export Mission' })).toBeVisible();
    // Close export dialog
    await page.keyboard.press('Escape');

    // Check Import
    await expect(page.getByRole('button', { name: 'Import Mission', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Import Mission', exact: true }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Import Mission' })).toBeVisible();
  });
});
