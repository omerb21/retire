import test from 'node:test';
import assert from 'node:assert/strict';
import { calculateNPVBreakdown } from './npvBreakdown.js';

const year = (yr, monthly, income, taxes = [], monthlyTax = 0) => ({
  year: yr, netMonthlyIncome: monthly, totalMonthlyTax: monthlyTax,
  incomeBreakdown: income, taxBreakdown: taxes,
});
const approx = (actual, expected) => assert.ok(
  Math.abs(actual - expected) < 0.01, 'expected ' + expected + ', got ' + actual
);

test('recurring pension: no lump sum and unchanged discount timing', () => {
  const result = calculateNPVBreakdown(
    [year(2026, 1000, [1000], [0]), year(2027, 1000, [1000], [0])], [], 1, 0
  );
  approx(result.recurringNpv, 12000 + 12000 / 1.03);
  approx(result.oneTimeNpv, 0);
  approx(result.totalEconomicValue, result.cashflowNpv);
});

test('one-time capital payment in a future projection year is counted once', () => {
  const result = calculateNPVBreakdown(
    [year(2026, 0, [0], [0]), year(2027, 1000, [1000], [0])],
    [{ monthly_income: 12000, current_value: 0, start_date: '2027-06-01' }], 0, 0
  );
  approx(result.projectedOneTimeNpv, 12000 / 1.03);
  approx(result.recurringNpv, 0);
  approx(result.remainingCapitalValue, 0);
});

test('recurring and lump sum in the same year are separated', () => {
  const result = calculateNPVBreakdown(
    [year(2026, 2000, [1000, 1000], [0, 0])],
    [{ monthly_income: 12000, current_value: 0, start_date: '2026-12-01' }], 1, 0
  );
  approx(result.recurringNpv, 12000);
  approx(result.projectedOneTimeNpv, 12000);
  approx(result.cashflowNpv, 24000);
});

test('future severance with API-normalized current_value is discounted, not added at face value', () => {
  const projection = Array.from({length: 5}, (_, n) => year(2026 + n, 0, [], []));
  const result = calculateNPVBreakdown(projection, [
    {asset_name: 'מענק פיצויים פטור', current_value: 66000, monthly_income: 0,
      start_date: '2030-11-02', tax_treatment: 'exempt'}
  ], 0, 0);
  approx(result.futureCapitalNpv, 66000 / (1.03 ** 4));
  approx(result.remainingCapitalValue, 0);
});

test('same asset with balance and projection payment cannot be counted twice', () => {
  const result = calculateNPVBreakdown(
    [year(2026, 1000, [1000], [0])],
    [{asset_name:'נכס',current_value:12000,monthly_income:12000,start_date:'2026-07-01'}],
    0, 0
  );
  approx(result.totalEconomicValue, 12000);
  assert.ok(result.warnings.some(s => s.includes('יתרה ותשלום')));
});

test('remaining unscheduled assets stay outside NPV and retain current value', () => {
  const result = calculateNPVBreakdown(
    [year(2026, 0, [], [])],
    [{current_value: 25000, monthly_income: 0, start_date:'2025-01-01'}], 0, 0
  );
  approx(result.oneTimeNpv, 0);
  approx(result.remainingCapitalValue, 25000);
});

test('tax mismatch is flagged, not silently recalculated', () => {
  const result = calculateNPVBreakdown(
    [year(2026, 1000, [1000], [250], 0)],
    [{current_value:0,monthly_income:12000,start_date:'2026-02-01',tax_treatment:'fixed_rate'}],
    0, 0
  );
  assert.ok(result.warnings.some(s => s.includes('אי התאמת מס')));
  approx(result.cashflowNpv, 12000);
  approx(result.recurringNpv, 0);
  approx(result.reconciliationNpv, 3000);
});

test('two future capital payments plus exempt severance are separate from pension PV', () => {
  const projection = Array.from({ length:5 }, (_, i) =>
    year(2026+i, i===4?44819:0, i===4?[694,26287,17838]:[0,0,0], [0,0,0])
  );
  const assets = [
    {current_value:66000,monthly_income:0,start_date:'2030-11-02',tax_treatment:'exempt'},
    {current_value:0,monthly_income:315448.66,start_date:'2030-11-02',tax_treatment:'exempt'},
    {current_value:0,monthly_income:214054.45,start_date:'2030-11-02',tax_treatment:'capital_gains'},
  ];
  const result = calculateNPVBreakdown(projection, assets, 1, 0);
  approx(result.futureCapitalNpv, 66000/(1.03**4));
  approx(result.remainingCapitalValue,0);
  approx(result.cashflowNpv,44819*12/(1.03**4));
  approx(result.cashflowNpv, result.recurringNpv+result.projectedOneTimeNpv);
});
