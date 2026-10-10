import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',timeout:60000,expect:{timeout:15000},use:{baseURL:process.env.NYAYAVAULT_TEST_URL||'http://127.0.0.1:3001',headless:true,viewport:{width:1440,height:1000}},reporter:[['list'],['json',{outputFile:'../docs/browser-test-results.json'}]]});
