//+------------------------------------------------------------------+
//|                                      V38_2_FeatureEngine.mqh     |
//|  MQL5 mirror of backend/v38/v38_2/m5_validation.py build_feature |
//|  Version: V38.2 FINAL (50 features — PRICE_INDICES only)        |
//|  Excludes 6 MACRO_NEWS features (contract indices 44-49).        |
//|  This MUST match the Python ONNX feature order exactly.         |
//+------------------------------------------------------------------+
#property strict
#ifndef __V38_2_FEATURE_ENGINE_MQH__
#define __V38_2_FEATURE_ENGINE_MQH__

//--- Feature contract version
#define V38_2_FEATURE_CONTRACT_VERSION "V38.2_final"
#define V38_2_N_FEATURES 50   // PRICE_INDICES only (excludes 6 MACRO_NEWS)

//--- ONNX model artifacts (place in MQL5/Files/v38_2/)
#define V38_2_ONNX_FILENAME "v38_2_final_model.onnx"
#define V38_2_CALIBRATOR_FILENAME "v38_2_calibrator.json"

//--- Label parameters (MUST match Python V38Config)
#define V38_2_LABEL_TP_R    2.0
#define V38_2_LABEL_SL_R    1.0
#define V38_2_LABEL_MAX_BARS 240   // M5 bars (~20 hours)
#define V38_2_THRESHOLD     0.50  // calibrated probability threshold

//=== ONNX feature indices (50 features) ============================
// These map directly to the ONNX model input tensor columns 0-49.
// Indices 0-43 = contract indices 0-43 (STRUCTURE through SESSION)
// Indices 44-49 = contract indices 50-55 (SETUP_GEOMETRY)
// EXCLUDED: contract indices 44-49 (MACRO_NEWS: event_present,
//          event_importance, normalized_surprise, surprise_zscore,
//          expected_gold_dir_enc, observed_reaction_atr)
//===================================================================

#define O_HTF_REGIME_ENC            0
#define O_LTF_REGIME_ENC            1
#define O_BOS_COUNT_RECENT          2
#define O_CHOCH_COUNT_RECENT         3
#define O_LAST_EVENT_DIRECTION_ENC  4
#define O_LAST_EVENT_DISP_ATR        5
#define O_LAST_EVENT_AGE_BARS       6
#define O_PROTECTED_HIGH            7
#define O_PROTECTED_LOW             8
#define O_MULTI_LEG_ALIGNED         9
#define O_LEG_EXTENSION_ATR        10
#define O_STRUCTURE_STRENGTH       11
#define O_NEAREST_LIQUIDITY_DIST   12
#define O_NEAREST_LIQUIDITY_SIDE   13
#define O_LIQUIDITY_SWEPT          14
#define O_SWEEP_DEPTH_ATR         15
#define O_POST_SWEEP_REACTION_ATR  16
#define O_EQH_EQL_PRESENT          17
#define O_INDUCEMENT_PRESENT       18
#define O_OB_PRESENT               19
#define O_OB_DIRECTION_ENC        20
#define O_OB_STRENGTH             21
#define O_OB_DISTANCE_ATR         22
#define O_OB_AGE_BARS             23
#define O_OB_MITIGATION_COUNT     24
#define O_OB_FRESHNESS_ENC        25
#define O_OB_MITIGATION_DEPTH     26
#define O_FVG_PRESENT             27
#define O_FVG_DIRECTION_ENC       28
#define O_FVG_SIZE_ATR            29
#define O_FVG_AGE_BARS            30
#define O_FVG_FILL_PCT            31
#define O_FVG_FRESHNESS_ENC       32
#define O_PD_POSITION             33
#define O_PD_LABEL_ENC            34
#define O_PD_DISTANCE_FROM_EQ     35
#define O_PD_LEG_SPAN_ATR         36
#define O_ATR                     37
#define O_ATR_PERCENTILE          38
#define O_DAILY_RANGE_PCT         39
#define O_VOLATILITY_REGIME_ENC   40
#define O_SPREAD                  41
#define O_SESSION_ENC             42
#define O_SESSION_PHASE_ENC       43
#define O_HTF_ALIGNMENT_ENC      44
#define O_LTF_ALIGNMENT_ENC      45
#define O_DISTANCE_TO_ENTRY_ATR   46
#define O_SL_DISTANCE_ATR         47
#define O_TP_DISTANCE_ATR         48
#define O_AVAILABLE_RR            49

//--- Categorical encodings (MUST match Python exactly)
// Regime: bearish=0, neutral=1, bullish=2
#define REG_BEARISH  0.0
#define REG_NEUTRAL  1.0
#define REG_BULLISH  2.0
// Direction: bearish=-1, neutral=0, bullish=1
#define DIR_BEARISH  (-1.0)
#define DIR_NEUTRAL  0.0
#define DIR_BULLISH  1.0
// Session: asian=0, london=1, overlap=2, ny=3, off=4
// OB freshness: fresh=1, touched=2, stale=3 (but Python uses 1,2,3)
// FVG freshness: open=1, partially_filled=2, fully_filled=3
// PD label: discount=0, equilibrium=1, premium=2
#define PD_DISCOUNT     0.0
#define PD_EQUILIBRIUM  1.0
#define PD_PREMIUM      2.0

#define NAN_SENTINEL 0.0

//+------------------------------------------------------------------+
//| Feature engine — computes the 50-float vector.                   |
//| Structure methods (BOS/CHOCH/OB/FVG/liquidity/PD) are virtual     |
//| shims returning 0.0/neutral when no object exists, matching       |
//| Python NAN_SENTINEL=0.0. The full structure module               |
//| (V38_2_Structure.mqh) overrides these for live trading.          |
//+------------------------------------------------------------------+
class CV38_2FeatureEngine
  {
protected:
   double            m_atrBuffer[];
   int               m_atrPeriod;
   int               m_atrPctLookback;
   double            m_sessionStarts[5];
   double            m_sessionEnds[5];

public:
   void              Init(int atrPeriod=14, int atrPctLookback=200);
   double            ATRAt(const string symbol, ENUM_TIMEFRAMES tf, int barIndex);
   double            ATRPercentile(const double &atrSeries[], int barIndex, int lookback);
   double            DailyRangePct(double barHigh, double barLow, double atrVal);
   int               VolatilityRegime(double atrPercentile);
   int               SessionEnc(datetime t);
   int               SessionPhaseEnc(datetime t);
   double            SLDistanceATR(double price, double refExtreme, double atrVal, bool isLong);
   double            TPDistanceATR(double slDistance, double tpR);
   double            AvailableRR(double slDistance, double tpDistance);

   // Structure-feature shims (overridden by V38_2_Structure.mqh)
   virtual double    HTFRegimeEnc(int htfBar);
   virtual double    LTFRegimeEnc(int ltfBar);
   virtual double    BOSCountRecent(int ltfBar);
   virtual double    CHOCHCountRecent(int ltfBar);
   virtual double    LastEventDirEnc(int ltfBar);
   virtual double    LastEventDispATR(int ltfBar);
   virtual double    LastEventAgeBars(int ltfBar);
   virtual double    ProtectedHigh(int ltfBar);
   virtual double    ProtectedLow(int ltfBar);
   virtual double    MinProtectedLow(int ltfBar, double fallback);
   virtual double    MaxProtectedHigh(int ltfBar, double fallback);
   virtual double    MultiLegAligned(int ltfBar);
   virtual double    LegExtensionATR(int ltfBar);
   virtual double    StructureStrength(int ltfBar);
   virtual double    NearestLiquidityDistATR(int ltfBar, double price, double atrVal);
   virtual double    NearestLiquiditySideEnc(int ltfBar, double price, double atrVal);
   virtual double    LiquiditySwept(int ltfBar);
   virtual double    SweepDepthATR(int ltfBar);
   virtual double    PostSweepReactionATR(int ltfBar);
   virtual double    EQHEQLPresent(int ltfBar);
   virtual double    InducementPresent(int ltfBar);
   virtual double    OBPresent(int ltfBar);
   virtual double    OBDirectionEnc(int ltfBar);
   virtual double    OBStrength(int ltfBar);
   virtual double    OBDistanceATR(int ltfBar, double price, double atrVal);
   virtual double    OBAgeBars(int ltfBar);
   virtual double    OBMitigationCount(int ltfBar);
   virtual double    OBFreshnessEnc(int ltfBar);
   virtual double    OBMitigationDepth(int ltfBar);
   virtual double    FVGPresent(int ltfBar);
   virtual double    FVGDirectionEnc(int ltfBar);
   virtual double    FVGSizeATR(int ltfBar);
   virtual double    FVGAgeBars(int ltfBar);
   virtual double    FVGFillPct(int ltfBar);
   virtual double    FVGFreshnessEnc(int ltfBar);
   virtual double    PDPosition(int ltfBar);
   virtual double    PDLabelEnc(int ltfBar);
   virtual double    PDDistanceFromEq(int ltfBar);
   virtual double    PDLegSpanATR(int ltfBar);
   virtual double    HTFAlignmentEnc(int ltfBar, string direction);
   virtual double    LTFAlignmentEnc(int ltfBar, string direction);
   // distance to entry zone (nearest OB then FVG edge). Mirrors Python
   // build_feature_vector v[52] (target = nearest OB/FVG edge or price).
   virtual double    DistanceToEntryATR(int ltfBar, double price, double atrVal);
   // Engine-resolved price/ATR/percentile so BuildVector does not depend on
   // the live series indexing (the StructureEngine uses its own buffered bars).
   virtual double    PriceAt(int ltfBar);
   virtual double    ATRValAt(int ltfBar);
   virtual double    ATRPercentileAt(int ltfBar);
   // Assemble the 50-vector (PRICE_INDICES only — no MACRO_NEWS)
   bool              BuildVector(int ltfBar, int htfBar, datetime t,
                                  string direction, double &outVector[]);
  };

//+------------------------------------------------------------------+
void CV38_2FeatureEngine::Init(int atrPeriod=14, int atrPctLookback=200)
  {
   m_atrPeriod = atrPeriod;
   m_atrPctLookback = atrPctLookback;
   m_sessionStarts[0]=0;  m_sessionEnds[0]=7;   // asian
   m_sessionStarts[1]=7;  m_sessionEnds[1]=12;  // london
   m_sessionStarts[2]=12; m_sessionEnds[2]=16;  // overlap
   m_sessionStarts[3]=16; m_sessionEnds[3]=21;  // ny
   m_sessionStarts[4]=21; m_sessionEnds[4]=24;  // off
  }

//--- Default bodies for structure-feature virtuals.
//    MQL5 has no pure-virtual (=0); the base must provide a body for every
//    declared function. These return neutral defaults (matching Python's
//    NaN_SENTINEL=0.0 / neutral-enc values) and are overridden by
//    CV38_2StructureEngine when a real structure engine is attached.
double CV38_2FeatureEngine::HTFRegimeEnc(int htfBar)            { return 1.0; }
double CV38_2FeatureEngine::LTFRegimeEnc(int ltfBar)           { return 1.0; }
double CV38_2FeatureEngine::BOSCountRecent(int ltfBar)         { return 0.0; }
double CV38_2FeatureEngine::CHOCHCountRecent(int ltfBar)       { return 0.0; }
double CV38_2FeatureEngine::LastEventDirEnc(int ltfBar)       { return 0.0; }
double CV38_2FeatureEngine::LastEventDispATR(int ltfBar)       { return 0.0; }
double CV38_2FeatureEngine::LastEventAgeBars(int ltfBar)       { return 0.0; }
double CV38_2FeatureEngine::ProtectedHigh(int ltfBar)          { return 0.0; }
double CV38_2FeatureEngine::ProtectedLow(int ltfBar)           { return 0.0; }
double CV38_2FeatureEngine::MultiLegAligned(int ltfBar)        { return 0.0; }
double CV38_2FeatureEngine::LegExtensionATR(int ltfBar)        { return 0.0; }
double CV38_2FeatureEngine::StructureStrength(int ltfBar)       { return 0.0; }
double CV38_2FeatureEngine::NearestLiquidityDistATR(int ltfBar, double price, double atrVal) { return 0.0; }
double CV38_2FeatureEngine::NearestLiquiditySideEnc(int ltfBar, double price, double atrVal)  { return 0.0; }
double CV38_2FeatureEngine::LiquiditySwept(int ltfBar)         { return 0.0; }
double CV38_2FeatureEngine::SweepDepthATR(int ltfBar)          { return 0.0; }
double CV38_2FeatureEngine::PostSweepReactionATR(int ltfBar)  { return 0.0; }
double CV38_2FeatureEngine::EQHEQLPresent(int ltfBar)          { return 0.0; }
double CV38_2FeatureEngine::InducementPresent(int ltfBar)      { return 0.0; }
double CV38_2FeatureEngine::OBPresent(int ltfBar)              { return 0.0; }
double CV38_2FeatureEngine::OBDirectionEnc(int ltfBar)         { return 0.0; }
double CV38_2FeatureEngine::OBStrength(int ltfBar)             { return 0.0; }
double CV38_2FeatureEngine::OBDistanceATR(int ltfBar, double price, double atrVal) { return 0.0; }
double CV38_2FeatureEngine::OBAgeBars(int ltfBar)               { return 0.0; }
double CV38_2FeatureEngine::OBMitigationCount(int ltfBar)      { return 0.0; }
double CV38_2FeatureEngine::OBFreshnessEnc(int ltfBar)         { return 1.0; }
double CV38_2FeatureEngine::OBMitigationDepth(int ltfBar)     { return 0.0; }
double CV38_2FeatureEngine::FVGPresent(int ltfBar)             { return 0.0; }
double CV38_2FeatureEngine::FVGDirectionEnc(int ltfBar)       { return 0.0; }
double CV38_2FeatureEngine::FVGSizeATR(int ltfBar)            { return 0.0; }
double CV38_2FeatureEngine::FVGAgeBars(int ltfBar)            { return 0.0; }
double CV38_2FeatureEngine::FVGFillPct(int ltfBar)            { return 0.0; }
double CV38_2FeatureEngine::FVGFreshnessEnc(int ltfBar)      { return 1.0; }
double CV38_2FeatureEngine::PDPosition(int ltfBar)            { return 0.5; }
double CV38_2FeatureEngine::PDLabelEnc(int ltfBar)            { return 1.0; }
double CV38_2FeatureEngine::PDDistanceFromEq(int ltfBar)      { return 0.0; }
double CV38_2FeatureEngine::PDLegSpanATR(int ltfBar)          { return 0.0; }
// HTFAlignmentEnc / LTFAlignmentEnc have real bodies further below.

double CV38_2FeatureEngine::ATRAt(const string symbol, ENUM_TIMEFRAMES tf, int barIndex)
  {
   int shift = (int)Bars(symbol, tf) - 1 - barIndex;
   int avail = shift + 1; // bars available up to this shift (inclusive)
   if(avail < 2) return 0.0;
   // Wilder smoothing; for the warmup portion (or when fewer than period bars
   // are available) fall back to a simple average of true range. MQL5 iATR is a
   // handle-based indicator (no shift arg), so compute TR manually here.
   int n = (avail < m_atrPeriod) ? avail : m_atrPeriod;
   if(n < 1) return 0.0;
   double sum=0.0;
   for(int k=0;k<n;k++)
     {
      int s=shift-k;
      double high=iHigh(symbol,tf,s);
      double low=iLow(symbol,tf,s);
      double prevClose=(s+1 < (int)Bars(symbol,tf)) ? iClose(symbol,tf,s+1) : low;
      double tr=MathMax(high-low, MathMax(MathAbs(high-prevClose), MathAbs(low-prevClose)));
      sum+=tr;
     }
   return sum/n;
  }

double CV38_2FeatureEngine::ATRPercentile(const double &atrSeries[], int barIndex, int lookback)
  {
   int lo=MathMax(0, barIndex-lookback);
   double cur=(barIndex<ArraySize(atrSeries))? atrSeries[barIndex] : 0.0;
   int count=0, total=0;
   for(int i=lo;i<=barIndex && i<ArraySize(atrSeries);i++)
     { total++; if(atrSeries[i]<=cur) count++; }
   return (total>0)? (double)count/total : 0.5;
  }

double CV38_2FeatureEngine::DailyRangePct(double barHigh, double barLow, double atrVal)
  {
   if(atrVal<=0) return 0.0;
   double r=barHigh-barLow;
   double v=MathMax(0.0, MathMin(1.0, (r/atrVal)/4.0));
   return v;
  }

int CV38_2FeatureEngine::VolatilityRegime(double atrPercentile)
  {
   double pct=atrPercentile*100.0;
   if(pct<25.0) return 0;
   if(pct>=75.0) return 2;
   return 1;
  }

int CV38_2FeatureEngine::SessionEnc(datetime t)
  {
   MqlDateTime dt; TimeToStruct(t, dt);
   for(int i=0;i<5;i++)
      if(dt.hour>=m_sessionStarts[i] && dt.hour<m_sessionEnds[i]) return i;
   return 4;
  }

int CV38_2FeatureEngine::SessionPhaseEnc(datetime t)
  {
   MqlDateTime dt; TimeToStruct(t, dt);
   int s=SessionEnc(t);
   double start=m_sessionStarts[s], end=m_sessionEnds[s];
   if(end==start) return 0;
   double frac=(dt.hour-start)/(end-start);
   if(frac<0.33) return 0;
   if(frac<0.66) return 1;
   return 2;
  }

double CV38_2FeatureEngine::SLDistanceATR(double price, double refExtreme, double atrVal, bool isLong)
  {
   if(atrVal<=0) return 0.0;
   double d = isLong ? (price-refExtreme) : (refExtreme-price);
   d = MathMax(atrVal*0.5, d);
   return d/atrVal;
  }

double CV38_2FeatureEngine::TPDistanceATR(double slDistance, double tpR)
  { return slDistance*tpR; }

double CV38_2FeatureEngine::AvailableRR(double slDistance, double tpDistance)
  { return (slDistance>0)? tpDistance/slDistance : 0.0; }

double CV38_2FeatureEngine::HTFAlignmentEnc(int ltfBar, string direction)
  {
   double reg=HTFRegimeEnc(ltfBar);
   string regName=(reg<0.5)?"bearish":((reg>1.5)?"bullish":"neutral");
   if(direction==regName) return 1.0;
   if(direction=="neutral"||regName=="neutral") return 0.0;
   return -1.0;
  }

double CV38_2FeatureEngine::LTFAlignmentEnc(int ltfBar, string direction)
  {
   double reg=LTFRegimeEnc(ltfBar);
   string regName=(reg<0.5)?"bearish":((reg>1.5)?"bullish":"neutral");
   if(direction==regName) return 1.0;
   if(direction=="neutral"||regName=="neutral") return 0.0;
   return -1.0;
  }

double CV38_2FeatureEngine::DistanceToEntryATR(int ltfBar, double price, double atrVal)
  {
   // Base shim: no OB/FVG object available → 0.0 (matches Python
   // when ob_idx and fvg_idx are both None). Overridden in StructureEngine.
   if(atrVal<=0) return 0.0;
   return 0.0;
  }

//--- Base shims for engine-resolved price/ATR/percentile/protected levels.
//    StructureEngine overrides these to use its own buffered bar arrays so
//    BuildVector never depends on live-series shift indexing.
double CV38_2FeatureEngine::PriceAt(int ltfBar)
  {
   return iClose(_Symbol, PERIOD_CURRENT, (int)Bars(_Symbol,0)-1-ltfBar);
  }
double CV38_2FeatureEngine::ATRValAt(int ltfBar)
  {
   return ATRAt(_Symbol, PERIOD_CURRENT, ltfBar);
  }
double CV38_2FeatureEngine::ATRPercentileAt(int ltfBar)
  {
   return ATRPercentile(m_atrBuffer, ltfBar, m_atrPctLookback);
  }
double CV38_2FeatureEngine::MinProtectedLow(int ltfBar, double fallback)
  {
   double v=ProtectedLow(ltfBar);
   return (v!=0.0)? v : fallback;
  }
double CV38_2FeatureEngine::MaxProtectedHigh(int ltfBar, double fallback)
  {
   double v=ProtectedHigh(ltfBar);
   return (v!=0.0)? v : fallback;
  }

//+------------------------------------------------------------------+
//| BuildVector — assembles the 50-feature ONNX input.               |
//| This is the CANONICAL V38.2 feature pipeline. It mirrors the     |
//| Python build_feature_vector() in m5_validation.py.               |
//+------------------------------------------------------------------+
bool CV38_2FeatureEngine::BuildVector(int ltfBar, int htfBar, datetime t,
                                       string direction, double &outVector[])
  {
   if(ArraySize(outVector)<V38_2_N_FEATURES) return false;
   // Engine-resolved price/ATR (StructureEngine uses its buffered bars)
   double price=PriceAt(ltfBar);
   double atrVal=ATRValAt(ltfBar);
   if(atrVal<=0) atrVal=1.0;

   outVector[O_HTF_REGIME_ENC]=HTFRegimeEnc(htfBar);
   outVector[O_LTF_REGIME_ENC]=LTFRegimeEnc(ltfBar);
   outVector[O_BOS_COUNT_RECENT]=BOSCountRecent(ltfBar);
   outVector[O_CHOCH_COUNT_RECENT]=CHOCHCountRecent(ltfBar);
   outVector[O_LAST_EVENT_DIRECTION_ENC]=LastEventDirEnc(ltfBar);
   outVector[O_LAST_EVENT_DISP_ATR]=LastEventDispATR(ltfBar);
   outVector[O_LAST_EVENT_AGE_BARS]=LastEventAgeBars(ltfBar);
   outVector[O_PROTECTED_HIGH]=ProtectedHigh(ltfBar);
   outVector[O_PROTECTED_LOW]=ProtectedLow(ltfBar);
   outVector[O_MULTI_LEG_ALIGNED]=MultiLegAligned(ltfBar);
   outVector[O_LEG_EXTENSION_ATR]=LegExtensionATR(ltfBar);
   outVector[O_STRUCTURE_STRENGTH]=StructureStrength(ltfBar);
   outVector[O_NEAREST_LIQUIDITY_DIST]=NearestLiquidityDistATR(ltfBar,price,atrVal);
   outVector[O_NEAREST_LIQUIDITY_SIDE]=NearestLiquiditySideEnc(ltfBar,price,atrVal);
   outVector[O_LIQUIDITY_SWEPT]=LiquiditySwept(ltfBar);
   outVector[O_SWEEP_DEPTH_ATR]=SweepDepthATR(ltfBar);
   outVector[O_POST_SWEEP_REACTION_ATR]=PostSweepReactionATR(ltfBar);
   outVector[O_EQH_EQL_PRESENT]=EQHEQLPresent(ltfBar);
   outVector[O_INDUCEMENT_PRESENT]=InducementPresent(ltfBar);
   outVector[O_OB_PRESENT]=OBPresent(ltfBar);
   outVector[O_OB_DIRECTION_ENC]=OBDirectionEnc(ltfBar);
   outVector[O_OB_STRENGTH]=OBStrength(ltfBar);
   outVector[O_OB_DISTANCE_ATR]=OBDistanceATR(ltfBar,price,atrVal);
   outVector[O_OB_AGE_BARS]=OBAgeBars(ltfBar);
   outVector[O_OB_MITIGATION_COUNT]=OBMitigationCount(ltfBar);
   outVector[O_OB_FRESHNESS_ENC]=OBFreshnessEnc(ltfBar);
   outVector[O_OB_MITIGATION_DEPTH]=OBMitigationDepth(ltfBar);
   outVector[O_FVG_PRESENT]=FVGPresent(ltfBar);
   outVector[O_FVG_DIRECTION_ENC]=FVGDirectionEnc(ltfBar);
   outVector[O_FVG_SIZE_ATR]=FVGSizeATR(ltfBar);
   outVector[O_FVG_AGE_BARS]=FVGAgeBars(ltfBar);
   outVector[O_FVG_FILL_PCT]=FVGFillPct(ltfBar);
   outVector[O_FVG_FRESHNESS_ENC]=FVGFreshnessEnc(ltfBar);
   outVector[O_PD_POSITION]=PDPosition(ltfBar);
   outVector[O_PD_LABEL_ENC]=PDLabelEnc(ltfBar);
   outVector[O_PD_DISTANCE_FROM_EQ]=PDDistanceFromEq(ltfBar);
   outVector[O_PD_LEG_SPAN_ATR]=PDLegSpanATR(ltfBar);
   outVector[O_ATR]=atrVal;
   outVector[O_ATR_PERCENTILE]=ATRPercentileAt(ltfBar);
   // daily range uses the same engine bar (parity with Python high_arr[b]/low_arr[b])
   outVector[O_DAILY_RANGE_PCT]=DailyRangePct(iHigh(_Symbol,0,(int)Bars(_Symbol,0)-1-ltfBar),
                                              iLow(_Symbol,0,(int)Bars(_Symbol,0)-1-ltfBar), atrVal);
   outVector[O_VOLATILITY_REGIME_ENC]=(double)VolatilityRegime(outVector[O_ATR_PERCENTILE]);
   // O_SPREAD parity restore: training units are PRICE (dollars), e.g.
   // f_spread p50=0.36, p99=1.53 in v38_2_dataset_M5_H1_lb240.parquet.
   // SYMBOL_SPREAD(points) * _Point converts natively on any digit count.
   outVector[O_SPREAD]=(double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD)
                       * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   outVector[O_SESSION_ENC]=(double)SessionEnc(t);
   outVector[O_SESSION_PHASE_ENC]=(double)SessionPhaseEnc(t);
   // NOTE: NO MACRO_NEWS features (contract indices 44-49 excluded)
   outVector[O_HTF_ALIGNMENT_ENC]=HTFAlignmentEnc(ltfBar,direction);
   outVector[O_LTF_ALIGNMENT_ENC]=LTFAlignmentEnc(ltfBar,direction);
   outVector[O_DISTANCE_TO_ENTRY_ATR]=DistanceToEntryATR(ltfBar,price,atrVal);
   // SL distance mirrors Python build_feature_vector v[53]:
   //   bullish: ref = min_protected_low(bar, price-a); sl_d = max(a*0.5, price-ref)
   //   bearish: ref = max_protected_high(bar, price+a); sl_d = max(a*0.5, ref-price)
   // The Min/Max protected-level helpers fall back to (price∓a) when no level
   // exists, exactly like the Python fallback.
   double refExtreme = (direction=="bullish") ? MinProtectedLow(ltfBar, price-atrVal)
                                              : MaxProtectedHigh(ltfBar, price+atrVal);
   outVector[O_SL_DISTANCE_ATR]=SLDistanceATR(price, refExtreme, atrVal, direction=="bullish");
   outVector[O_TP_DISTANCE_ATR]=TPDistanceATR(outVector[O_SL_DISTANCE_ATR], V38_2_LABEL_TP_R);
   outVector[O_AVAILABLE_RR]=AvailableRR(outVector[O_SL_DISTANCE_ATR], outVector[O_TP_DISTANCE_ATR]);
   return true;
  }

#endif // __V38_2_FEATURE_ENGINE_MQH__
