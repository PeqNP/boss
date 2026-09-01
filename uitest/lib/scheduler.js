// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

/**
 * Building a scheduler world for a test to run in.
 *
 * The app's own seeds, reaching its own routes — the shared part is in
 * `seed.js`. Everything here goes through the API rather than the screens, so
 * what is seeded is valid by construction: a business that can take a booking
 * really can, and a confirmed appointment really holds its slot.
 *
 * Caller must be signed in as the operator of the business being built.
 */

import { expect } from "@playwright/test";

const API = "/api/io.bithead.scheduler";

async function post(page, url, data) {
  const response = await page.request.post(`${API}${url}`, data ? { data } : {});
  expect(response.ok(), `POST ${url} failed: ${await response.text()}`).toBe(true);
  return response.json();
}

async function put(page, url, data) {
  const response = await page.request.put(`${API}${url}`, { data });
  expect(response.ok(), `PUT ${url} failed: ${await response.text()}`).toBe(true);
  return response.json();
}

/**
 * A business that can take a booking: hours, a service, and somebody to do it.
 *
 * @param {import('@playwright/test').Page} page
 * @param {number} businessId - from `POST /signup`
 * @returns {Promise<{jobTypeId: number, sizeId: number, employeeId: number}>}
 */
export async function readyToBook(page, businessId) {
  const at = (path) => `/business/${businessId}${path}`;

  // Open every day, so a seeded date does not have to dodge a closed one.
  const hours = [];
  for (let day = 0; day < 7; day++) {
    hours.push({ dayOfWeek: day, openTime: "08:00", closeTime: "18:00",
                 isClosed: false });
  }
  await put(page, at("/config"), {
    slotIncrementMinutes: 15, minBookingNoticeHours: 0, cutoffDays: 90,
    operatingHours: hours
  });

  // A job type is created as a draft and named by the save that follows, which
  // is also what makes it active — a draft reaches no customer.
  const jobType = await post(page, at("/job-type"), { name: "Haircut" });
  await put(page, at(`/job-type/${jobType.id}`),
            { name: "Haircut", minEmployees: 1, isActive: true });
  const size = await post(page, at(`/job-type/${jobType.id}/size`),
                          { name: "Standard", durationMinutes: 60, cost: 40 });

  const employee = await post(page, at("/employee"),
                              { firstName: "Alice", lastName: "Kim" });
  await put(page, at(`/employee/${employee.id}`), {
    firstName: "Alice", lastName: "Kim", includeInSchedule: true,
    jobTypeIds: [jobType.id]
  });
  for (let day = 0; day < 7; day++) {
    await post(page, at(`/employee/${employee.id}/schedule`),
               { dayOfWeek: day, startTime: "08:00", endTime: "18:00" });
  }

  return { jobTypeId: jobType.id, sizeId: size.id, employeeId: employee.id };
}

/**
 * One confirmed appointment, held through the kiosk the way a customer makes it.
 *
 * The kiosk needs no account, so this works signed in as anybody or as nobody.
 *
 * @param {import('@playwright/test').Page} page
 * @param {number} businessId
 * @param {{jobTypeId: number, sizeId: number}} what - from `readyToBook`
 * @param {string} date - YYYY-MM-DD
 * @param {string} time - HH:MM
 * @returns {Promise<number>} the job id
 */
export async function book(page, businessId, what, date, time) {
  const session = await post(page, `/kiosk/${businessId}/session`, {
    jobTypeId: what.jobTypeId, sizeId: what.sizeId,
    scheduledDate: date, scheduledTime: time
  });
  await post(page, `/kiosk/session/${session.sessionId}/confirm`,
             { contactData: [], attributeData: [] });
  return session.jobId;
}
