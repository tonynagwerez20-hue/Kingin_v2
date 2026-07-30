//+------------------------------------------------------------------+
//|  ONNX MT5 Integration - ML Trading Signal Filter                 |
//+------------------------------------------------------------------+
//|  This EA uses a trained ML model to filter trading signals       |
//|  based on technical analysis features.                           |
//+------------------------------------------------------------------+
//|  FEATURE INDEX MAPPING (MUST MATCH PYTHON SCRIPT):               |
//|  [0] ob_strength        : Order block strength (0.0-1.0)          |
//|  [1] fvg_present        : Fair value gap present (0 or 1)        |
//|  [2] bos_aligned        : Break of structure aligned (0 or 1)    |
//|  [3] liquidity_swept    : Liquidity swept (0 or 1)               |
//|  [4] adr_pct            : ADR percentage (0.0-1.0)              |
//|  [5] pips_to_liquidity : Pips to next liquidity (0-100)         |
//|  [6] session            : Trading session (0=asian,1=london,    |
//|                            2=overlap, 3=ny)                     |
//|  [7] htf_bias           : Higher timeframe bias (-1 to 1)       |
//+------------------------------------------------------------------+
//|  REQUIREMENTS:                                                   |
//|  - OnnxRun with fixed batch size of 1                            |
//|  - Input shape: float[1,8]                                       |
//+------------------------------------------------------------------+

#property copyright "AI Generated"
#property link      ""
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+
input string   ModelFileName = "lgbm_signal_filter_20y.onnx"; // ONNX model filename
input double   MinConfidence = 0.65;                          // Minimum confidence to trade
input bool     UseMLFilter = true;                            // Enable ML signal filter
input ulong    MagicNumber = 123456;                          // EA Magic Number

//+------------------------------------------------------------------+
//| GLOBAL VARIABLES                                                 |
//+------------------------------------------------------------------+
CTrade         trade;
int            onnxHandle = INVALID_HANDLE;
bool           g_b彩色 = false;

// Feature indices (must match ONNX model input order)
enum FeatureIndex
{
   FEATURE_OB_STRENGTH = 0,
   FEATURE_FVG_PRESENT = 1,
   FEATURE_BOS_ALIGNED = 2,
   FEATURE_LIQUIDITY_SWEP = 3,
   FEATURE_ADR_PCT = 4,
   FEATURE_PIPS_TO_LIQ = 5,
   FEATURE_SESSION = 6,
   FEATURE_HTF_BIAS = 7,
   NUM_FEATURES = 8
};

//+------------------------------------------------------------------+
//| Session mapping                                                   |
//+------------------------------------------------------------------+
int GetSessionIndex(ENUM_TIMEFRAMES timeframe)
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   
   int hour = dt.hour;
   
   // Asian: 0-6, London: 8-12, Overlap: 12-16, NY: 8-12 (simplified)
   if(hour >= 0 && hour < 7) return 0;      // Asian
   if(hour >= 7 && hour < 12) return 1;    // London
   if(hour >= 12 && hour < 16) return 2;    // Overlap
   return 3;                                 // NY
}

//+------------------------------------------------------------------+
//| Calculate technical indicators                                   |
//+------------------------------------------------------------------+
double GetOBStrength(int shift)
{
   // Order Block strength estimation
   // Replace with your actual OB detection logic
   double high = iHigh(_Symbol, PERIOD_CURRENT, shift);
   double low = iLow(_Symbol, PERIOD_CURRENT, shift);
   double close = iClose(_Symbol, PERIOD_CURRENT, shift);
   
   // Simple range-based estimation
   double range = high - low;
   if(range < _Point) return 0.5;
   
   double position = (close - low) / range;
   return NormalizeDouble(position, 2);
}

bool IsFVGPresent(int shift)
{
   // Fair Value Gap detection
   // Look for a gap between candle bodies
   double high1 = iHigh(_Symbol, PERIOD_CURRENT, shift + 2);
   double low1 = iLow(_Symbol, PERIOD_CURRENT, shift + 2);
   double high2 = iHigh(_Symbol, PERIOD_CURRENT, shift + 1);
   double low2 = iLow(_Symbol, PERIOD_CURRENT, shift + 1);
   
   // Bullish FVG: gap up
   if(high1 < low2) return true;
   
   // Bearish FVG: gap down  
   if(low1 > high2) return true;
   
   return false;
}

bool IsBOSAligned(int shift, ENUM_TRADE_DIRECTION direction)
{
   // Break of Structure detection
   // Replace with your actual BOS detection
   double high0 = iHigh(_Symbol, PERIOD_CURRENT, shift);
   double low0 = iLow(_Symbol, PERIOD_CURRENT, shift);
   double high1 = iHigh(_Symbol, PERIOD_CURRENT, shift + 1);
   double low1 = iLow(_Symbol, PERIOD_CURRENT, shift + 1);
   
   if(direction == TRADE_DIRECTION_BUY)
      return (high0 > high1); // Break of highs
   else
      return (low0 < low1);   // Break of lows
}

bool IsLiquiditySwept(int shift)
{
   // Liquidity sweep detection
   // Look for price spikes that take out recent highs/lows
   double high1 = iHigh(_Symbol, PERIOD_CURRENT, shift + 3);
   double low1 = iLow(_Symbol, PERIOD_CURRENT, shift + 3);
   double close2 = iClose(_Symbol, PERIOD_CURRENT, shift + 2);
   
   // Check if close is back inside after spike
   if(close2 < high1 && close2 > low1)
      return true;
      
   return false;
}

double GetADRPct()
{
   // Average Day Range percentage
   double atr = iATR(_Symbol, PERIOD_CURRENT, 14);
   double dailyATR = atr * 24; // Convert to daily scale
   
   double high = iHigh(_Symbol, PERIOD_D1, 0);
   double low = iLow(_Symbol, PERIOD_D1, 0);
   double range = high - low;
   
   if(range < _Point) return 0.5;
   return NormalizeDouble(dailyATR / range, 2);
}

double GetPipsToLiquidity()
{
   // Calculate pips to nearest liquidity (swing high/low)
   double price = iClose(_Symbol, PERIOD_CURRENT, 0);
   double swingHigh = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double swingLow = iLow(_Symbol, PERIOD_CURRENT, 1);
   
   double pipsUp = (swingHigh - price) / _Point;
   double pipsDown = (price - swingLow) / _Point;
   
   // Return smaller distance in pips
   return MathMin(pipsUp, pipsDown) / 10.0; // Convert to proper pip units
}

double GetHTFBias()
{
   // Higher timeframe trend bias
   // Check H4 trend
   double h4Close = iClose(_Symbol, PERIOD_H4, 0);
   double h4MA = iMA(_Symbol, PERIOD_H4, 50, 0, MODE_SMA, PRICE_CLOSE);
   
   if(h4Close > h4MA) return 1.0;
   if(h4Close < h4MA) return -1.0;
   return 0.0;
}

//+------------------------------------------------------------------+
//| Load ONNX Model                                                  |
//+------------------------------------------------------------------+
bool LoadONNXModel()
{
   string filename = "MQL5\\Files\\" + ModelFileName;
   
   // Get file content using resource
   uchar modelData[];
   ResetLastError();
   
   // Method 1: Using OnnxCreateFromBuffer (recommended for MT5)
   // The model file must be in MQL5\Files folder
   if(!FileSelectDialog("Select ONNX Model", NULL, "ONNX Files (*.onnx)|*.onnx", FSD_FILE_SELECT, filename))
   {
      Print("ONNX model file selection cancelled or failed");
      return false;
   }
   
   long fileHandle = FileOpen(filename, FILE_READ | FILE_BINARY);
   if(fileHandle == INVALID_HANDLE)
   {
      Print("Failed to open ONNX file: ", filename, " Error: ", GetLastError());
      return false;
   }
   
   int fileSize = (int)FileSize(fileHandle);
   ArrayResize(modelData, fileSize);
   FileReadArray(fileHandle, modelData, 0, fileSize);
   FileClose(fileHandle);
   
   // Create ONNX session with fixed batch size of 1
   onnxHandle = OnnxCreateFromBuffer(modelData, ONNX_DEFAULT);
   
   if(onnxHandle == INVALID_HANDLE)
   {
      Print("Failed to create ONNX session. Error: ", GetLastError());
      Print("Make sure OnnxRun is supported in this MT5 build.");
      return false;
   }
   
   Print("✓ ONNX model loaded successfully: ", filename);
   Print("  Handle: ", onnxHandle);
   
   return true;
}

//+------------------------------------------------------------------+
//| Prepare Feature Vector                                           |
//+------------------------------------------------------------------+
bool PrepareFeatureVector(float &features[], ENUM_TRADE_DIRECTION direction)
{
   if(ArraySize(features) != NUM_FEATURES)
      ArrayResize(features, NUM_FEATURES);
   
   // [0] ob_strength
   features[FEATURE_OB_STRENGTH] = (float)GetOBStrength(0);
   
   // [1] fvg_present (binary)
   features[FEATURE_FVG_PRESENT] = IsFVGPresent(0) ? 1.0f : 0.0f;
   
   // [2] bos_aligned (binary)
   features[FEATURE_BOS_ALIGNED] = IsBOSAligned(0, direction) ? 1.0f : 0.0f;
   
   // [3] liquidity_swept (binary)
   features[FEATURE_LIQUIDITY_SWEP] = IsLiquiditySwept(0) ? 1.0f : 0.0f;
   
   // [4] adr_pct (0-1)
   features[FEATURE_ADR_PCT] = (float)GetADRPct();
   
   // [5] pips_to_liquidity (0-100)
   features[FEATURE_PIPS_TO_LIQ] = (float)GetPipsToLiquidity();
   
   // [6] session (0-3)
   features[FEATURE_SESSION] = (float)GetSessionIndex(PERIOD_CURRENT);
   
   // [7] htf_bias (-1 to 1)
   features[FEATURE_HTF_BIAS] = (float)GetHTFBias();
   
   return true;
}

//+------------------------------------------------------------------+
//| Run ONNX Model and Get Prediction                                |
//+------------------------------------------------------------------+
double RunONNXModel(const float &features[])
{
   if(onnxHandle == INVALID_HANDLE)
   {
      Print("ONNX handle is invalid!");
      return 0.5; // Return neutral confidence
   }
   
   // Prepare input tensor [1, 8] - MUST be fixed batch size of 1 for MT5
   long inputShape[] = {1, NUM_FEATURES};
   vectorf inputVector = vectorf::Constant(NUM_FEATURES, 0.0f);
   
   for(int i = 0; i < NUM_FEATURES; i++)
      inputVector[i] = features[i];
   
   // Create input tensor
   vectorf outputVector;
   
   // Run inference
   bool success = OnnxRun(onnxHandle, ONNX_NO_CONVERSION, inputVector, outputVector);
   
   if(!success)
   {
      Print("ONNX inference failed! Error: ", GetLastError());
      return 0.5;
   }
   
   // Extract probability (first output)
   double probability = (double)outputVector[0];
   
   // Sanity check
   if(probability < 0.0 || probability > 1.0)
   {
      Print("Warning: Probability out of range: ", probability);
      probability = MathMax(0.0, MathMin(1.0, probability));
   }
   
   return probability;
}

//+------------------------------------------------------------------+
//| Should Trade - Main ML Decision Function                         |
//+------------------------------------------------------------------+
bool ShouldTradeML(ENUM_TRADE_DIRECTION direction, double &confidence)
{
   if(!UseMLFilter)
   {
      confidence = 1.0;
      return true;
   }
   
   if(onnxHandle == INVALID_HANDLE)
   {
      Print("Warning: ONNX not loaded, using default behavior");
      confidence = 0.5;
      return false;
   }
   
   // Prepare features
   float features[];
   if(!PrepareFeatureVector(features, direction))
   {
      Print("Failed to prepare feature vector");
      confidence = 0.5;
      return false;
   }
   
   // Debug: Print features
   #ifdef _DEBUG
      string featureStr = "Features: ";
      for(int i = 0; i < NUM_FEATURES; i++)
      {
         featureStr += StringFormat("[%d]=%.2f ", i, features[i]);
      }
      Print(featureStr);
   #endif
   
   // Run model
   confidence = RunONNXModel(features);
   
   // Decision based on confidence threshold
   bool shouldTrade = (confidence >= MinConfidence);
   
   Print("ML Decision: ", shouldTrade ? "TRADE" : "SKIP", 
         " | Confidence: ", DoubleToString(confidence, 4),
         " | Threshold: ", DoubleToString(MinConfidence, 2));
   
   return shouldTrade;
}

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("===========================================");
   Print("ML Trading Signal Filter EA Initializing");
   Print("===========================================");
   
   // Initialize trade class
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationPoints(10);
   trade.SetTypeFilling(ORDER_FILLING_FOK);
   
   // Load ONNX model
   if(!LoadONNXModel())
   {
      Print("WARNING: ONNX model not loaded. ML filtering disabled.");
      Print("EA will operate without ML signal filter.");
      return INIT_SUCCEEDED; // Don't fail init, just disable ML
   }
   
   Print("===========================================");
   Print("EA Initialized Successfully");
   Print("===========================================");
   
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // Release ONNX handle
   if(onnxHandle != INVALID_HANDLE)
   {
      OnnxRelease(onnxHandle);
      Print("ONNX handle released");
   }
   
   Comment("");
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
   // Your main trading logic here
   // Example:
   //
   // ENUM_TRADE_DIRECTION direction = DetectSetup();
   // double confidence = 0;
   //
   // if(ShouldTradeML(direction, confidence))
   // {
   //    // Execute trade
   //    ExecuteTrade(direction);
   // }
}

//+------------------------------------------------------------------+
//| Example: Trade execution                                          |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_TRADE_DIRECTION direction)
{
   double price, sl, tp;
   double volume = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   
   if(direction == TRADE_DIRECTION_BUY)
   {
      price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      sl = price - 100 * _Point;
      tp = price + 200 * _Point;
      
      trade.Buy(volume, _Symbol, price, sl, tp, "ML Signal");
   }
   else if(direction == TRADE_DIRECTION_SELL)
   {
      price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      sl = price + 100 * _Point;
      tp = price - 200 * _Point;
      
      trade.Sell(volume, _Symbol, price, sl, tp, "ML Signal");
   }
}

//+------------------------------------------------------------------+
//| Helper: Detect trade setup (implement your own logic)            |
//+------------------------------------------------------------------+
ENUM_TRADE_DIRECTION DetectSetup()
{
   // Your setup detection logic here
   // This is just a placeholder
   return TRADE_DIRECTION_BUY; // or SELL, or NEUTRAL
}

//+------------------------------------------------------------------+
