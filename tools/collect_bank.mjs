/**
 * [INPUT]: 依赖 Ego Lite 的 TaskSpace 与当前登录会话；依赖 Node.js 文件接口。
 * [OUTPUT]: 导出 collectBank；保存六套题库清单和原始题目字段。
 * [POS]: tools 的只读采集器；build_bank.py 读取其文件并去重导出。
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import fs from "node:fs/promises";
import path from "node:path";

const BANKS = [
  ["564", "人工3级近期新增高频理论题3"],
  ["558", "人工3级近期新增高频理论题2"],
  ["548", "人工3级近期新增高频理论题1"],
  ["530", "人工3级单选"],
  ["529", "人工3级判断"],
  ["528", "人工3级多选"],
];
const SOURCE = "https://tx.jiexunkeji.net/app/index.php";
const BATCH_SIZE = 30;

function sourceUrl(id) {
  return `${SOURCE}?i=36&c=entry&id=${id}&do=practice_exec&m=online_testapp`;
}

async function readJson(filename) {
  try {
    return JSON.parse(await fs.readFile(filename, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

async function openBank(page, id) {
  const current = new URL(await page.url());
  if (current.searchParams.get("id") !== id || current.searchParams.get("do") !== "practice_exec") {
    await page.goto(sourceUrl(id), { timeout: 30000 });
  }
  await page.waitForFunction(
    bankId => typeof PracticeApp !== "undefined" && String(PracticeApp.practice_id) === bankId,
    id,
    { timeout: 10000 },
  );
}

function checkBatch(response, entries) {
  if (response.result !== "SUCCESS" || !response.data || typeof response.data !== "object") {
    throw new Error("读题接口未返回成功的题目集合。");
  }
  const wanted = new Map(entries.map(entry => [String(entry.index), String(entry.id)]));
  const seen = new Set();
  for (const question of Object.values(response.data)) {
    const index = String(question.index);
    if (seen.has(index) || wanted.get(index) !== String(question.id)) {
      throw new Error(`返回题目与清单不一致：索引 ${index}。`);
    }
    seen.add(index);
  }
  if (seen.size !== wanted.size) {
    throw new Error(`本批缺题：请求 ${wanted.size}，返回 ${seen.size}。`);
  }
}

async function updateRawMap(rawDir) {
  const files = (await fs.readdir(rawDir)).filter(name => name.endsWith(".json")).sort();
  const members = files.map(name => {
    const bank = name.split(/[._]/)[0];
    const role = name.endsWith(".manifest.json") ? "完整 ID 与来源清单" : "原始题目批次";
    return `${name}: 题库 ${bank} 的${role}。`;
  });
  await fs.writeFile(path.join(rawDir, "CLAUDE.md"), [
    "# question_bank/raw/",
    "> L2 | 父级: ../CLAUDE.md",
    "",
    "清单记录每套题库的完整 ID 和顺序。",
    "批次保留接口原始题目字段。",
    "data 首批是数组，后续是索引字典。",
    "认证字段不进入文件。已验证批次支持续采。",
    "",
    "成员清单",
    ...members,
    "",
    "[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md",
    "",
  ].join("\n"));
}

/** 每轮限制请求数，避免长时间占用浏览器控制。 */
export async function collectBank(task, { root, maxBatches = 15 } = {}) {
  if (!root || !path.isAbsolute(root)) throw new Error("root 必须是项目的绝对路径。");
  const rawDir = path.join(root, "question_bank", "raw");
  await fs.mkdir(rawDir, { recursive: true });
  const page = task.page("p1");
  const manifests = [];

  // ---- 清单：只读取题目索引、ID 和题型 ----
  for (const [id, name] of BANKS) {
    const filename = path.join(rawDir, `${id}.manifest.json`);
    let manifest = await readJson(filename);
    if (!manifest) {
      await openBank(page, id);
      manifest = await page.evaluate(() => ({
        bank_id: String(PracticeApp.practice_id),
        total: Number(PracticeApp.total),
        source_url: location.href,
        type_labels: PracticeApp.type_label,
        type_base: PracticeApp.custom_base,
        entries: Object.entries(PracticeApp.questions).map(([index, question]) => ({
          index, id: String(question.id), type: question.type,
        })),
      }));
      manifest.name = name;
      manifest.captured_at = new Date().toISOString();
      if (manifest.total !== manifest.entries.length) throw new Error(`题库 ${id} 的总数与 ID 清单不符。`);
      await fs.writeFile(filename, JSON.stringify(manifest, null, 2) + "\n");
    }
    manifests.push(manifest);
  }
  await updateRawMap(rawDir);

  // ---- 原始批次：动态读取当前页路由，不保存认证参数 ----
  let fetchedBatches = 0;
  for (const manifest of manifests) {
    for (let start = 0; start < manifest.entries.length; start += BATCH_SIZE) {
      const entries = manifest.entries.slice(start, start + BATCH_SIZE);
      const filename = path.join(rawDir, `${manifest.bank_id}_${String(start).padStart(4, "0")}.json`);
      const existing = await readJson(filename);
      if (existing) {
        checkBatch(existing, entries);
        continue;
      }
      if (fetchedBatches >= maxBatches) break;
      await openBank(page, manifest.bank_id);
      const ids = Object.fromEntries(entries.map(entry => [entry.index, entry.id]));
      const response = await page.evaluate(async ids => {
        if (PracticeApp.r.getQuestion !== "&r=Practice.getQuestion") {
          throw new Error("当前页面的读题路由与已验证接口不符。");
        }
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 15000);
        try {
          const result = await fetch(PracticeApp.url_base + PracticeApp.r.getQuestion, {
            method: "POST", credentials: "same-origin",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: "data=" + encodeURIComponent(btoa(JSON.stringify({ ids }))),
            signal: controller.signal,
          });
          if (!result.ok) throw new Error(`HTTP ${result.status}`);
          const payload = await result.json();
          return { result: payload.result, data: payload.data };
        } finally {
          clearTimeout(timer);
        }
      }, ids);
      checkBatch(response, entries);
      await fs.writeFile(filename, JSON.stringify(response, null, 2) + "\n");
      fetchedBatches++;
    }
    if (fetchedBatches >= maxBatches) break;
  }
  await updateRawMap(rawDir);

  const banks = [];
  for (const manifest of manifests) {
    let captured = 0;
    for (let start = 0; start < manifest.entries.length; start += BATCH_SIZE) {
      const filename = path.join(rawDir, `${manifest.bank_id}_${String(start).padStart(4, "0")}.json`);
      const response = await readJson(filename);
      if (response) {
        checkBatch(response, manifest.entries.slice(start, start + BATCH_SIZE));
        captured += Object.keys(response.data).length;
      }
    }
    banks.push({ id: manifest.bank_id, name: manifest.name, expected: manifest.total, captured });
  }
  return {
    fetchedBatches, banks,
    expected: banks.reduce((sum, bank) => sum + bank.expected, 0),
    captured: banks.reduce((sum, bank) => sum + bank.captured, 0),
    complete: banks.every(bank => bank.expected === bank.captured),
  };
}
