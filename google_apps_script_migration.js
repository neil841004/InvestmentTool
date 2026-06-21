const SPREADSHEET_ID = "1XbhOfdR1835_HOgoFTR6SmUshI32t7c_W57VtgWV78Y";

const TARGET_HEADERS = [
  "ticker",
  "custom_name",
  "note",
  "rating",
  "yahoo_url",
  "tradingview_url",
  "tags",
  "display_order",
  "created_at",
  "avg_cost",
  "shares",
];

const CASH_TICKER = "CASH_TWD";
const CASH_DISPLAY_NAME = "持有現金";
const SETTINGS_HEADERS = ["refresh_interval", "tag_colors", "default_period"];

function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);
    assertAuthorized(payload);

    const action = payload.action || (payload.targets ? "import_all" : "");
    let result;

    if (action === "import_all") {
      result = importInvestmentToolData(payload);
    } else if (action === "load_watchlist") {
      result = { items: loadWatchlist() };
    } else if (action === "save_watchlist") {
      result = saveWatchlist(payload.items || []);
    } else if (action === "migrate_schema") {
      result = migrateSheetSchema();
    } else if (action === "load_settings") {
      result = { settings: loadSettings() };
    } else if (action === "save_settings") {
      result = saveSettings(payload.settings || {});
    } else if (action === "load_all") {
      result = {
        items: loadWatchlist(),
        settings: loadSettings(),
      };
    } else {
      throw new Error("Unknown action: " + action);
    }

    return jsonResponse({ ok: true, ...result });
  } catch (error) {
    return jsonResponse({ ok: false, error: String(error && error.message ? error.message : error) });
  }
}

function doGet() {
  return jsonResponse({ ok: true, service: "InvestmentTool Google Sheets storage" });
}

function assertAuthorized(payload) {
  const expectedToken = PropertiesService.getScriptProperties().getProperty("MIGRATION_TOKEN");
  if (!expectedToken || payload.token !== expectedToken) {
    throw new Error("Invalid migration token.");
  }
}

function importInvestmentToolData(payload) {
  const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  const targets = mergeTargetsWithAssets(payload.targets || [], payload.assets || []);

  writeTable(spreadsheet, "targets", TARGET_HEADERS, targets);
  writeTable(spreadsheet, "settings", SETTINGS_HEADERS, payload.settings || []);

  return {
    targets: targets.length,
    assets_merged: (payload.assets || []).length,
    settings: (payload.settings || []).length,
  };
}

function loadWatchlist() {
  const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  const targets = loadMergedTargets(spreadsheet);

  return targets
    .map((target) => {
      const ticker = cleanString(target.ticker);
      const avgCost = toNumber(target.avg_cost);
      const shares = toNumber(target.shares);

      return {
        ticker,
        custom_name: cleanString(target.custom_name),
        note: cleanString(target.note),
        rating: toInteger(target.rating),
        yahoo_url: cleanString(target.yahoo_url),
        tradingview_url: cleanString(target.tradingview_url),
        tags: parseTags(target.tags),
        display_order: toInteger(target.display_order),
        created_at: cleanString(target.created_at),
        avg_cost: avgCost,
        shares,
        holding: shares > 0,
      };
    })
    .filter((item) => item.ticker)
    .sort((a, b) => a.display_order - b.display_order || a.ticker.localeCompare(b.ticker));
}

function migrateSheetSchema() {
  const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  const targets = loadMergedTargets(spreadsheet);
  removeSheetIfPresent(spreadsheet, "assets");
  return {
    targets: targets.length,
    cash_row: targets.some((target) => isCashTicker(target.ticker)),
    assets_removed: !spreadsheet.getSheetByName("assets"),
  };
}

function saveWatchlist(items) {
  const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  const now = new Date().toISOString();

  const targets = items.map((item, index) => ({
    ticker: cleanString(item.ticker),
    custom_name: cleanString(item.custom_name),
    note: cleanString(item.note),
    rating: toInteger(item.rating),
    yahoo_url: cleanString(item.yahoo_url),
    tradingview_url: cleanString(item.tradingview_url),
    tags: stringifyTags(item.tags),
    display_order: index,
    created_at: cleanString(item.created_at) || now,
    avg_cost: toNumber(item.avg_cost, isCashTicker(item.ticker) ? 1 : 0),
    shares: toNumber(item.shares),
  })).filter((item) => item.ticker);

  const normalizedTargets = ensureCashTargetRow(targets);
  writeTable(spreadsheet, "targets", TARGET_HEADERS, normalizedTargets);

  return { targets: normalizedTargets.length };
}

function loadMergedTargets(spreadsheet) {
  const targets = readTable(spreadsheet, "targets");
  const assets = readTable(spreadsheet, "assets");
  const mergedTargets = mergeTargetsWithAssets(targets, assets);

  if (targetsNeedRewrite(targets, mergedTargets)) {
    writeTable(spreadsheet, "targets", TARGET_HEADERS, mergedTargets);
  }

  return mergedTargets;
}

function mergeTargetsWithAssets(targets, assets) {
  const assetsByTicker = {};
  assets.forEach((asset) => {
    const ticker = cleanString(asset.ticker);
    if (ticker) {
      assetsByTicker[ticker] = asset;
    }
  });

  const mergedTargets = targets
    .map((target, index) => {
      const ticker = cleanString(target.ticker);
      const asset = assetsByTicker[ticker] || {};
      const avgCost = hasValue(target.avg_cost) ? toNumber(target.avg_cost) : toNumber(asset.avg_cost);
      const shares = hasValue(target.shares) ? toNumber(target.shares) : toNumber(asset.shares);

      return {
        ticker,
        custom_name: cleanString(target.custom_name),
        note: cleanString(target.note),
        rating: toInteger(target.rating),
        yahoo_url: cleanString(target.yahoo_url),
        tradingview_url: cleanString(target.tradingview_url),
        tags: stringifyTags(parseTags(target.tags)),
        display_order: hasValue(target.display_order) ? toInteger(target.display_order) : index,
        created_at: cleanString(target.created_at),
        avg_cost: isCashTicker(ticker) && avgCost <= 0 ? 1 : avgCost,
        shares,
      };
    })
    .filter((target) => target.ticker);

  return ensureCashTargetRow(mergedTargets);
}

function ensureCashTargetRow(targets) {
  const now = new Date().toISOString();
  let hasCash = false;
  let maxOrder = -1;

  const normalizedTargets = targets.map((target) => {
    const displayOrder = toInteger(target.display_order);
    maxOrder = Math.max(maxOrder, displayOrder);

    if (!isCashTicker(target.ticker)) {
      return target;
    }

    hasCash = true;
    return {
      ...target,
      ticker: CASH_TICKER,
      custom_name: cleanString(target.custom_name) || CASH_DISPLAY_NAME,
      yahoo_url: "",
      tradingview_url: "",
      avg_cost: toNumber(target.avg_cost, 1) > 0 ? toNumber(target.avg_cost, 1) : 1,
      shares: toNumber(target.shares),
    };
  });

  if (!hasCash) {
    normalizedTargets.push({
      ticker: CASH_TICKER,
      custom_name: CASH_DISPLAY_NAME,
      note: "",
      rating: 0,
      yahoo_url: "",
      tradingview_url: "",
      tags: "",
      display_order: maxOrder + 1,
      created_at: now,
      avg_cost: 1,
      shares: 0,
    });
  }

  return normalizedTargets;
}

function targetsNeedRewrite(originalTargets, mergedTargets) {
  if (originalTargets.length !== mergedTargets.length) {
    return true;
  }

  return originalTargets.some((target, index) => {
    const merged = mergedTargets[index] || {};
    return !hasOwn(target, "avg_cost") ||
      !hasOwn(target, "shares") ||
      hasOwn(target, "holding") ||
      toNumber(target.avg_cost) !== toNumber(merged.avg_cost) ||
      toNumber(target.shares) !== toNumber(merged.shares);
  });
}

function loadSettings() {
  const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  const rows = readTable(spreadsheet, "settings");
  const row = rows[0] || {};
  return {
    refresh_interval: toInteger(row.refresh_interval, 60),
    tag_colors: cleanString(row.tag_colors) || "{}",
    default_period: cleanString(row.default_period) || "1M",
  };
}

function saveSettings(settings) {
  const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  const row = {
    refresh_interval: toInteger(settings.refresh_interval, 60),
    tag_colors: typeof settings.tag_colors === "string" ? settings.tag_colors : JSON.stringify(settings.tag_colors || {}),
    default_period: cleanString(settings.default_period) || "1M",
  };

  writeTable(spreadsheet, "settings", SETTINGS_HEADERS, [row]);
  return { settings: 1 };
}

function readTable(spreadsheet, sheetName) {
  const sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet || sheet.getLastRow() < 1 || sheet.getLastColumn() < 1) {
    return [];
  }

  const values = sheet.getRange(1, 1, sheet.getLastRow(), sheet.getLastColumn()).getValues();
  const headers = values.shift().map((header) => cleanString(header));

  return values
    .filter((row) => row.some((cell) => cell !== ""))
    .map((row) => {
      const record = {};
      headers.forEach((header, index) => {
        if (header) {
          record[header] = row[index];
        }
      });
      return record;
    });
}

function writeTable(spreadsheet, sheetName, headers, rows) {
  const sheet = getOrCreateSheet(spreadsheet, sheetName);
  sheet.clearContents();

  const values = [headers].concat(
    rows.map((row) => headers.map((header) => row[header] === undefined || row[header] === null ? "" : row[header]))
  );

  sheet.getRange(1, 1, values.length, headers.length).setValues(values);
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, headers.length);
}

function getOrCreateSheet(spreadsheet, sheetName) {
  return spreadsheet.getSheetByName(sheetName) || spreadsheet.insertSheet(sheetName);
}

function removeSheetIfPresent(spreadsheet, sheetName) {
  const sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    return false;
  }

  if (spreadsheet.getSheets().length <= 1) {
    sheet.clearContents();
    return false;
  }

  spreadsheet.deleteSheet(sheet);
  return true;
}

function parseTags(value) {
  if (Array.isArray(value)) {
    return value.map((tag) => cleanString(tag)).filter(Boolean);
  }

  const text = cleanString(value);
  if (!text) {
    return [];
  }

  if (text.charAt(0) === "[") {
    try {
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed)) {
        return parsed.map((tag) => cleanString(tag)).filter(Boolean);
      }
    } catch (error) {
      // Fall back to comma splitting below.
    }
  }

  return text.split(",").map((tag) => tag.trim()).filter(Boolean);
}

function stringifyTags(value) {
  if (Array.isArray(value)) {
    return value.map((tag) => cleanString(tag)).filter(Boolean).join(",");
  }
  return cleanString(value);
}

function toNumber(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : (fallback === undefined ? 0 : fallback);
}

function toInteger(value, fallback) {
  return Math.trunc(toNumber(value, fallback === undefined ? 0 : fallback));
}

function toBoolean(value) {
  if (value === true || value === false) {
    return value;
  }
  if (typeof value === "number") {
    return value !== 0;
  }
  const text = cleanString(value).toLowerCase();
  return ["true", "1", "yes", "y", "持有", "持有中"].indexOf(text) >= 0;
}

function isCashTicker(ticker) {
  return cleanString(ticker).toUpperCase() === CASH_TICKER;
}

function hasValue(value) {
  return value !== undefined && value !== null && cleanString(value) !== "";
}

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function cleanString(value) {
  if (value === undefined || value === null) {
    return "";
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  return String(value).trim();
}

function jsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
