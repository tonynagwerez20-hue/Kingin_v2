//+------------------------------------------------------------------+
//|                                       V38_2_Structure.mqh        |
//|  MQL5 port of Python StructureIndex + structure engines.         |
//|  Mirrors: v38/structure/swing_engine.py                         |
//|           v38/structure/structure_engine.py (BOS/CHOCH/regime)  |
//|           v38/structure/ob_engine.py                              |
//|           v38/structure/liquidity_engine.py                      |
//|           v38/structure/fvg_engine.py                             |
//|           v38/structure/pd_engine.py                             |
//|           v38/v38_2/m5_validation.py StructureIndex              |
//|                                                                  |
//|  This is the SMC structure detection module. It maintains swings, |
//|  BOS/CHOCH events, order blocks, FVGs, liquidity pools, PD zones  |
//|  and provides per-bar leakage-safe queries.                      |
//|                                                                  |
//|  PARITY NOTE: Every algorithm mirrors the Python implementation. |
//|  Where MQL5 limitations require approximation, it is documented.   |
//+------------------------------------------------------------------+
#property strict
#ifndef __V38_2_STRUCTURE_MQH__
#define __V38_2_STRUCTURE_MQH__

#include <V38_2_FeatureEngine.mqh>

//--- Structure configuration (mirrors V38Config) -------------------
#define V38_2_SWING_STRENGTH        2      // fractal k
#define V38_2_SWING_MIN_SPACING     1
#define V38_2_BOS_CLOSE_REQUIRED    false  // wick-based break
#define V38_2_BOS_MIN_ATR_MULT      0.10
#define V38_2_CHOCH_MIN_ATR_MULT    0.30
#define V38_2_DISP_ATR_PERIOD       14
#define V38_2_OB_MAX_AGE_BARS       200
#define V38_2_OB_CLOSE_THROUGH_INV  true
#define V38_2_FVG_MIN_SIZE_ATR      0.05
#define V38_2_EQH_EQL_ATR_TOL       0.15
#define V38_2_LIQ_CLUSTER_ATR      0.25
#define V38_2_PD_EQ_BAND           0.10
#define V38_2_MIN_SETUP_QUALITY    0.30
#define V38_2_POOL_SWEEP_LOOKBACK  10
#define V38_2_EQ_LOOKBACK         100
#define V38_2_IND_LOOKBACK         50
#define V38_2_EV_COUNT_WINDOW      50

//--- Direction encoding (mirrors Python) ---------------------------
#define DIR_ENC_BULL   1.0
#define DIR_ENC_NEUT   0.0
#define DIR_ENC_BEAR  -1.0
#define REG_ENC_BULL   2.0
#define REG_ENC_NEUT   1.0
#define REG_ENC_BEAR   0.0

//+------------------------------------------------------------------+
//| Data structures                                                  |
//+------------------------------------------------------------------+
struct V38_2Swing
  {
   int      bar_index;
   datetime ts;
   double   price;
   int      kind;        // 1=high, -1=low
   int      strength;
   int      conf_bar;    // confirmation bar
   datetime conf_ts;
   bool     external;
   double   atr_at_conf;
  };

struct V38_2Event
  {
   int      bar_index;
   datetime ts;
   string   event_type;  // "BOS" | "CHOCH"
   int      direction;   // 1=bullish, -1=bearish
   double   broken_level;
   double   break_price;
   double   disp;        // displacement
   double   disp_atr;
   double   quality;
   int      conf_bar;
   datetime conf_ts;
  };

struct V38_2ProtectedLevel
  {
   int      kind;        // 1=high, -1=low
   double   price;
   string   swing_id;
   int      bar_index;
   int      conf_bar;
   int      status;      // 0=active, 1=broken, 2=superseded
  };

struct V38_2OrderBlock
  {
   int      source_bar;
   double   open, high, low, close;
   int      direction;   // 1=bullish, -1=bearish
   double   disp_atr;
   int      creation_bar;
   int      conf_bar;
   double   upper, lower, mid;
   bool     invalidated;
   int      inv_bar;
   int      mitigation_count;
   string   freshness;   // "fresh"|"touched"|"stale"
   string   lifecycle;   // "fresh"|"touched"|"partially_consumed"|"fully_consumed"|"invalidated"
   double   deepest_pen;
   double   quality;
  };

struct V38_2FVG
  {
   int      direction;   // 1=bullish, -1=bearish
   double   upper, lower, mid;
   double   size_atr;
   int      creation_bar;
   int      conf_bar;
   bool     invalidated;
   int      inv_bar;
   string   lifecycle;   // "open"|"partially_filled"|"fully_filled"|"invalidated"
   double   fill_pct;
  };

struct V38_2Pool
  {
   int      type;        // 1=high, -1=low
   double   price;
   int      creation_bar;
   int      conf_bar;
   int      touches;
   double   strength;
   bool     invalidated;
   bool     swept;
   int      sweep_bar;
   double   sweep_depth_atr;
   double   post_sweep_atr;
  };

struct V38_2EqualLevel
  {
   int      conf_bar;
   int      type;
  };

struct V38_2Inducement
  {
   int      conf_bar;
  };

struct V38_2Leg
  {
   int      direction;   // 1=bullish, -1=bearish
   double   start_price, end_price;
   double   high, low, equilibrium;
   int      start_bar, end_bar;
   int      conf_bar;
  };

struct V38_2PDState
  {
   int      leg_idx;     // -1 if none
   double   leg_high, leg_low, equilibrium;
   double   position;    // 0..1
   int      pd_label;    // 0=discount, 1=equilibrium, 2=premium, -1=unknown
   double   distance_from_eq;
   bool     valid;
  };

//+------------------------------------------------------------------+
//| Structure engine — maintains all SMC objects for one timeframe.  |
//| Mirrors Python MarketStructure + StructureIndex.                 |
//+------------------------------------------------------------------+
class CV38_2StructureEngine : public CV38_2FeatureEngine
  {
private:
   // Bar data buffers (maintained incrementally)
   double            m_open[];
   double            m_high[];
   double            m_low[];
   double            m_close[];
   datetime          m_ts[];
   double            m_spread[];
   double            m_atr[];
   int               m_nBars;

   // Structure objects (dynamic arrays)
   V38_2Swing        m_swings[];
   V38_2Event        m_events[];
   V38_2ProtectedLevel m_prots[];
   V38_2OrderBlock   m_obs[];
   V38_2FVG          m_fvgs[];
   V38_2Pool         m_pools[];
   V38_2EqualLevel   m_eqs[];
   V38_2Inducement   m_inds[];
   V38_2Leg          m_legs[];

   // Counters
   int               m_nSwings, m_nEvents, m_nProts, m_nObs, m_nFvgs;
   int               m_nPools, m_nEqs, m_nInds, m_nLegs;

   // Running state (mirrors Python StructureEngine.build loop)
   int               m_regime;       // 0=bear, 1=neutral, 2=bull
   int               m_lastProtHighIdx;  // index into m_prots, -1 if none
   int               m_lastProtLowIdx;
   int               m_lastExtHighIdx;   // index into m_swings
   int               m_lastExtLowIdx;
   int               m_lastBcEventIdx;   // last BOS/CHOCH event index
   int               m_evPtr;            // pointer for event adoption

   // Per-bar precomputed arrays (for O(1) queries)
   int               m_regArr[];          // regime per bar
   double            m_protMaxHigh[];     // max active prot high per bar
   double            m_protMinLow[];      // min active prot low per bar
   bool              m_hasObBull[];       // has valid OB bullish
   bool              m_hasObBear[];
   bool              m_hasObAnyBull[];    // no lifecycle filter
   bool              m_hasObAnyBear[];
   bool              m_hasFvgBull[];
   bool              m_hasFvgBear[];
   bool              m_hasSweptPool[];
   bool              m_sweptRecent[];
   double            m_sweepDepth[];
   double            m_sweepReaction[];
   bool              m_eqPresent[];
   bool              m_indPresent[];
   double            m_lastBcQuality[];
   double            m_lastEvDir[];
   double            m_lastEvDisp[];
   double            m_lastEvAge[];
   int               m_nBosLast50[];
   int               m_nChochLast50[];
   bool              m_last3ChochBull[];
   bool              m_last3ChochBear[];
   double            m_poolMaxPrice[];
   double            m_poolMinPrice[];

   // HTF data
   CV38_2StructureEngine *m_htf;  // pointer to HTF engine
   bool              m_isHtf;

   // Internal flag
   bool              m_initialized;
   string            m_symbol;
   ENUM_TIMEFRAMES   m_tf;

public:
   void              Init(string symbol, ENUM_TIMEFRAMES tf, bool isHtf=false);
   void              SetHTF(CV38_2StructureEngine *htf) { m_htf = htf; }
   bool              UpdateBar(datetime barTs, double o, double h, double l,
                                double c, double spread);
   void              FinalizeBar();  // recompute per-bar arrays after new bar
   int               NBars() { return m_nBars; }
   datetime          TsAt(int bar) { return (bar>=0 && bar<m_nBars)? m_ts[bar] : 0; }
   double            CloseAt(int bar) { return (bar>=0 && bar<m_nBars)? m_close[bar] : 0; }
   double            HighAt(int bar) { return (bar>=0 && bar<m_nBars)? m_high[bar] : 0; }
   double            LowAt(int bar) { return (bar>=0 && bar<m_nBars)? m_low[bar] : 0; }
   double            ATRAtIdx(int bar) { return (bar>=0 && bar<m_nBars)? m_atr[bar] : 0; }
   int               RegimeAt(int bar);
   string            RegimeStrAt(int bar);

   //--- StructureIndex query methods (override virtual shims) ---
   virtual double    HTFRegimeEnc(int htfBar);
   virtual double    LTFRegimeEnc(int ltfBar);
   virtual double    BOSCountRecent(int ltfBar);
   virtual double    CHOCHCountRecent(int ltfBar);
   virtual double    LastEventDirEnc(int ltfBar);
   virtual double    LastEventDispATR(int ltfBar);
   virtual double    LastEventAgeBars(int ltfBar);
   virtual double    ProtectedHigh(int ltfBar);
   virtual double    ProtectedLow(int ltfBar);
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
   // Overrides for engine-resolved price/ATR/percentile/entry-distance using
   // the StructureEngine's own buffered bar arrays (parity with Python).
   virtual double    DistanceToEntryATR(int ltfBar, double price, double atrVal);
   virtual double    PriceAt(int ltfBar);
   virtual double    ATRValAt(int ltfBar);
   virtual double    ATRPercentileAt(int ltfBar);
   virtual double    MinProtectedLow(int ltfBar, double fallback);
   virtual double    MaxProtectedHigh(int ltfBar, double fallback);

   // Setup detection (mirrors detect_and_build_m5 candidate checks)
   bool              IsCandidateSetup(int bar, string direction);

private:
   void              DetectSwings();
   void              DetectStructure();
   void              DetectOBs();
   void              DetectFVGs();
   void              DetectLiquidity();
   void              DetectPD();
   void              ComputeATR();
   void              PrecomputeQueries();
   double            ComputeATRVal(int bar);
   int               HTFBarForLTF(int ltfBar);
   double            NearestOB(int bar, double price, double atrVal, int &outIdx);
   int               NearestFVG(int bar, double price, double atrVal);
   double            Alignment(double regVal, string direction);
  };

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
void CV38_2StructureEngine::Init(string symbol, ENUM_TIMEFRAMES tf, bool isHtf=false)
  {
   m_symbol = symbol;
   m_tf = tf;
   m_isHtf = isHtf;
   m_nBars = 0;
   m_nSwings = 0; m_nEvents = 0; m_nProts = 0; m_nObs = 0; m_nFvgs = 0;
   m_nPools = 0; m_nEqs = 0; m_nInds = 0; m_nLegs = 0;
   m_regime = 1; // neutral
   m_lastProtHighIdx = -1; m_lastProtLowIdx = -1;
   m_lastExtHighIdx = -1; m_lastExtLowIdx = -1;
   m_lastBcEventIdx = -1; m_evPtr = 0;
   m_htf = NULL;
   m_initialized = true;
   CV38_2FeatureEngine::Init(V38_2_DISP_ATR_PERIOD, 200);
  }

//+------------------------------------------------------------------+
//| Compute ATR (Wilder) for all bars                                |
//+------------------------------------------------------------------+
void CV38_2StructureEngine::ComputeATR()
  {
   if(m_nBars < 2) return;
   int period = V38_2_DISP_ATR_PERIOD;
   ArrayResize(m_atr, m_nBars);
   // True Range
   double tr[];
   ArrayResize(tr, m_nBars);
   tr[0] = m_high[0] - m_low[0];
   for(int i=1; i<m_nBars; i++)
     {
      double pc = m_close[i-1];
      tr[i] = MathMax(m_high[i]-m_low[i],
                      MathMax(MathAbs(m_high[i]-pc), MathAbs(m_low[i]-pc)));
     }
   // Wilder smoothing
   if(m_nBars <= period)
     {
      double sum=0;
      for(int i=0;i<m_nBars;i++) sum+=tr[i];
      for(int i=0;i<m_nBars;i++) m_atr[i] = sum/m_nBars;
     }
   else
     {
      double sum=0;
      for(int i=0;i<period;i++) sum+=tr[i];
      m_atr[period-1] = sum/period;
      for(int i=period; i<m_nBars; i++)
         m_atr[i] = (m_atr[i-1]*(period-1) + tr[i]) / period;
      // fill early bars with simple average
      double avg = m_atr[period-1];
      for(int i=0;i<period-1;i++) m_atr[i] = avg;
     }
   // Guard against zero
   for(int i=0;i<m_nBars;i++)
      if(m_atr[i] <= 0) m_atr[i] = 1.0;
  }

double CV38_2StructureEngine::ComputeATRVal(int bar)
  {
   if(bar < 0 || bar >= m_nBars) return 1.0;
   double a = m_atr[bar];
   return (a > 0) ? a : 1.0;
  }

//+------------------------------------------------------------------+
//| Add a new bar to the engine                                       |
//+------------------------------------------------------------------+
bool CV38_2StructureEngine::UpdateBar(datetime barTs, double o, double h, double l,
                                       double c, double spread)
  {
   // Append bar data
   m_nBars++;
   ArrayResize(m_open, m_nBars);
   ArrayResize(m_high, m_nBars);
   ArrayResize(m_low, m_nBars);
   ArrayResize(m_close, m_nBars);
   ArrayResize(m_ts, m_nBars);
   ArrayResize(m_spread, m_nBars);
   m_open[m_nBars-1] = o;
   m_high[m_nBars-1] = h;
   m_low[m_nBars-1] = l;
   m_close[m_nBars-1] = c;
   m_ts[m_nBars-1] = barTs;
   m_spread[m_nBars-1] = spread;

   ComputeATR();
   DetectSwings();
   DetectStructure();
   DetectOBs();
   DetectFVGs();
   DetectLiquidity();
   DetectPD();
   PrecomputeQueries();
   return true;
  }

//+------------------------------------------------------------------+
//| Swing detection — fractal pivots with strength k                 |
//| Mirrors SwingEngine.detect()                                     |
//+------------------------------------------------------------------+
void CV38_2StructureEngine::DetectSwings()
  {
   int k = V38_2_SWING_STRENGTH;
   if(m_nBars < 2*k+1) return;

   // Only check the latest possible pivot (m_nBars - 1 - k)
   // A pivot at index i is confirmed at i+k
   int i = m_nBars - 1 - k;
   if(i < k) return;

   // Check if we already have this swing
   for(int s=0; s<m_nSwings; s++)
      if(m_swings[s].bar_index == i) return;

   double hh = m_high[i];
   double ll = m_low[i];
   bool isHigh = true, isLow = true;

   for(int j=1; j<=k; j++)
     {
      if(m_high[i-j] >= hh || m_high[i+j] >= hh) isHigh = false;
      if(m_low[i-j] <= ll || m_low[i+j] <= ll) isLow = false;
     }

   if(!isHigh && !isLow) return;

   // Enforce min spacing — replace if too close
   int kind = isHigh ? 1 : -1;
   int lastSameKind = -1;
   for(int s=m_nSwings-1; s>=0; s--)
     {
      if(m_swings[s].kind == kind)
        { lastSameKind = s; break; }
     }

   if(lastSameKind >= 0 && i - m_swings[lastSameKind].bar_index < V38_2_SWING_MIN_SPACING)
     {
      // Replace if more extreme
      bool replace = false;
      if(kind == 1 && hh > m_swings[lastSameKind].price) replace = true;
      if(kind == -1 && ll < m_swings[lastSameKind].price) replace = true;
      if(replace)
         m_swings[lastSameKind].bar_index = i;
      else
         return;
     }
   else
     {
      m_nSwings++;
      ArrayResize(m_swings, m_nSwings);
      m_swings[m_nSwings-1].bar_index = i;
     }

   int idx = (lastSameKind >= 0 && i - m_swings[lastSameKind].bar_index < V38_2_SWING_MIN_SPACING)
             ? lastSameKind : m_nSwings-1;
   m_swings[idx].ts = m_ts[i];
   m_swings[idx].price = (kind==1) ? hh : ll;
   m_swings[idx].kind = kind;
   m_swings[idx].strength = k;
   m_swings[idx].conf_bar = i + k;
   m_swings[idx].conf_ts = m_ts[i+k];
   m_swings[idx].atr_at_conf = ComputeATRVal(i+k);

   // Classify external: high external if higher than previous 2 highs
   m_swings[idx].external = false;
   int prevCount = 0;
   double prev1 = 0, prev2 = 0;
   for(int s=idx-1; s>=0 && prevCount<2; s--)
     {
      if(m_swings[s].kind == kind)
        {
         if(prevCount==0) prev1 = m_swings[s].price;
         else prev2 = m_swings[s].price;
         prevCount++;
        }
     }
   if(prevCount >= 2)
     {
      if(kind == 1 && hh > MathMax(prev1, prev2)) m_swings[idx].external = true;
      if(kind == -1 && ll < MathMin(prev1, prev2)) m_swings[idx].external = true;
     }

   // Update last external swing pointers
   if(m_swings[idx].external)
     {
      if(kind == 1) m_lastExtHighIdx = idx;
      else m_lastExtLowIdx = idx;
     }
  }

//+------------------------------------------------------------------+
//| Structure detection — BOS/CHOCH, protected levels, regime        |
//| Mirrors StructureEngine.build()                                  |
//+------------------------------------------------------------------+
void CV38_2StructureEngine::DetectStructure()
  {
   // Process the latest bar for break detection
   if(m_nBars < 2) return;
   int b = m_nBars - 1;

   // Adopt newly confirmed external swings (conf_bar <= b)
   // This is handled in DetectSwings when we update lastExtHigh/LowIdx

   double bar_atr = ComputeATRVal(b);
   double close = m_close[b];
   double high = m_high[b];
   double low = m_low[b];

   // Check bullish break of protected high
   if(m_lastProtHighIdx >= 0)
     {
      V38_2ProtectedLevel pl = m_prots[m_lastProtHighIdx];
      if(pl.status == 0 || pl.status == 2) // active or superseded
        {
         double broken_price = pl.price;
         bool broke = V38_2_BOS_CLOSE_REQUIRED ? (close > broken_price) : (high > broken_price);
         if(broke)
           {
            double disp = close - broken_price;
            double disp_atr = disp / bar_atr;
            bool is_choch = (m_regime == 0 || m_regime == 1) &&
                            (disp_atr >= V38_2_CHOCH_MIN_ATR_MULT);
            bool is_bos = (m_regime == 2) && (disp_atr >= V38_2_BOS_MIN_ATR_MULT);
            if(is_choch || is_bos)
              {
               m_nEvents++;
               ArrayResize(m_events, m_nEvents);
               int e = m_nEvents - 1;
               m_events[e].bar_index = b;
               m_events[e].ts = m_ts[b];
               m_events[e].event_type = is_choch ? "CHOCH" : "BOS";
               m_events[e].direction = 1; // bullish
               m_events[e].broken_level = broken_price;
               m_events[e].break_price = high;
               m_events[e].disp = disp;
               m_events[e].disp_atr = disp_atr;
               m_events[e].quality = MathMin(1.0, disp_atr / (V38_2_CHOCH_MIN_ATR_MULT * 3));
               m_events[e].conf_bar = b;
               m_events[e].conf_ts = m_ts[b];
               m_prots[m_lastProtHighIdx].status = 1; // broken
               if(is_choch)
                  m_regime = 2; // bullish
               m_lastBcEventIdx = e;
              }
           }
        }
     }

   // Check bearish break of protected low
   if(m_lastProtLowIdx >= 0)
     {
      V38_2ProtectedLevel pl = m_prots[m_lastProtLowIdx];
      if(pl.status == 0 || pl.status == 2)
        {
         double broken_price = pl.price;
         bool broke = V38_2_BOS_CLOSE_REQUIRED ? (close < broken_price) : (low < broken_price);
         if(broke)
           {
            double disp = broken_price - close;
            double disp_atr = disp / bar_atr;
            bool is_choch = (m_regime == 2 || m_regime == 1) &&
                            (disp_atr >= V38_2_CHOCH_MIN_ATR_MULT);
            bool is_bos = (m_regime == 0) && (disp_atr >= V38_2_BOS_MIN_ATR_MULT);
            if(is_choch || is_bos)
              {
               m_nEvents++;
               ArrayResize(m_events, m_nEvents);
               int e = m_nEvents - 1;
               m_events[e].bar_index = b;
               m_events[e].ts = m_ts[b];
               m_events[e].event_type = is_choch ? "CHOCH" : "BOS";
               m_events[e].direction = -1; // bearish
               m_events[e].broken_level = broken_price;
               m_events[e].break_price = low;
               m_events[e].disp = disp;
               m_events[e].disp_atr = disp_atr;
               m_events[e].quality = MathMin(1.0, disp_atr / (V38_2_CHOCH_MIN_ATR_MULT * 3));
               m_events[e].conf_bar = b;
               m_events[e].conf_ts = m_ts[b];
               m_prots[m_lastProtLowIdx].status = 1; // broken
               if(is_choch)
                  m_regime = 0; // bearish
               m_lastBcEventIdx = e;
              }
           }
        }
     }

   // Update protected levels from newly confirmed external swings
   // (external swings become protected when confirmed)
   if(m_lastExtHighIdx >= 0)
     {
      V38_2Swing sw = m_swings[m_lastExtHighIdx];
      if(sw.conf_bar <= b)
        {
         // Check if we already have this protected level
         bool exists = false;
         for(int p=0; p<m_nProts; p++)
            if(m_prots[p].kind == 1 && m_prots[p].price == sw.price &&
               m_prots[p].conf_bar == sw.conf_bar)
              { exists = true; break; }
         if(!exists)
           {
            // Supersede previous active high
            if(m_lastProtHighIdx >= 0 && m_prots[m_lastProtHighIdx].status == 0)
               m_prots[m_lastProtHighIdx].status = 2;
            m_nProts++;
            ArrayResize(m_prots, m_nProts);
            int p = m_nProts - 1;
            m_prots[p].kind = 1;
            m_prots[p].price = sw.price;
            m_prots[p].swing_id = "";
            m_prots[p].bar_index = sw.bar_index;
            m_prots[p].conf_bar = sw.conf_bar;
            m_prots[p].status = 0; // active
            m_lastProtHighIdx = p;
           }
        }
     }
   if(m_lastExtLowIdx >= 0)
     {
      V38_2Swing sw = m_swings[m_lastExtLowIdx];
      if(sw.conf_bar <= b)
        {
         bool exists = false;
         for(int p=0; p<m_nProts; p++)
            if(m_prots[p].kind == -1 && m_prots[p].price == sw.price &&
               m_prots[p].conf_bar == sw.conf_bar)
              { exists = true; break; }
         if(!exists)
           {
            if(m_lastProtLowIdx >= 0 && m_prots[m_lastProtLowIdx].status == 0)
               m_prots[m_lastProtLowIdx].status = 2;
            m_nProts++;
            ArrayResize(m_prots, m_nProts);
            int p = m_nProts - 1;
            m_prots[p].kind = -1;
            m_prots[p].price = sw.price;
            m_prots[p].swing_id = "";
            m_prots[p].bar_index = sw.bar_index;
            m_prots[p].conf_bar = sw.conf_bar;
            m_prots[p].status = 0;
            m_lastProtLowIdx = p;
           }
        }
     }

   // Build legs from external swings (opposite polarity pairs)
   // Simple: check if we have a new leg ending at the latest external swing
   if(m_lastExtHighIdx >= 0 || m_lastExtLowIdx >= 0)
     {
      // Find last two external swings of opposite kind
      int lastHigh = -1, lastLow = -1;
      for(int s=m_nSwings-1; s>=0; s--)
        {
         if(!m_swings[s].external) continue;
         if(m_swings[s].kind == 1 && lastHigh < 0) lastHigh = s;
         if(m_swings[s].kind == -1 && lastLow < 0) lastLow = s;
         if(lastHigh >= 0 && lastLow >= 0) break;
        }
      if(lastHigh >= 0 && lastLow >= 0)
        {
         int endIdx = (m_swings[lastHigh].conf_bar > m_swings[lastLow].conf_bar) ?
                       lastHigh : lastLow;
         int startIdx = (endIdx == lastHigh) ? lastLow : lastHigh;
         bool exists = false;
         for(int l=0; l<m_nLegs; l++)
            if(m_legs[l].conf_bar == m_swings[endIdx].conf_bar)
              { exists = true; break; }
         if(!exists)
           {
            m_nLegs++;
            ArrayResize(m_legs, m_nLegs);
            int l = m_nLegs - 1;
            V38_2Swing startSw = m_swings[startIdx];
            V38_2Swing endSw = m_swings[endIdx];
            m_legs[l].direction = (startSw.kind == -1 && endSw.kind == 1) ? 1 : -1;
            m_legs[l].start_price = startSw.price;
            m_legs[l].end_price = endSw.price;
            m_legs[l].high = MathMax(startSw.price, endSw.price);
            m_legs[l].low = MathMin(startSw.price, endSw.price);
            m_legs[l].equilibrium = (m_legs[l].high + m_legs[l].low) / 2.0;
            m_legs[l].start_bar = startSw.conf_bar;
            m_legs[l].end_bar = endSw.conf_bar;
            m_legs[l].conf_bar = endSw.conf_bar;
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Order Block detection (mirrors OrderBlockEngine.build)           |
//+------------------------------------------------------------------+
void CV38_2StructureEngine::DetectOBs()
  {
   // Check if the latest event created a new OB
   if(m_nEvents == 0) return;
   int evIdx = m_nEvents - 1;
   V38_2Event ev = m_events[evIdx];

   // Check if we already have an OB for this event bar
   for(int o=0; o<m_nObs; o++)
      if(m_obs[o].creation_bar == ev.bar_index) return;

   int b = ev.bar_index;
   int lookback = MathMax(1, V38_2_SWING_STRENGTH + 1);
   int start = MathMax(0, b - lookback);
   int obCandleIdx = -1;

   if(ev.direction == 1) // bullish break -> last down candle
     {
      for(int j=b-1; j>=start; j--)
         if(m_close[j] < m_open[j]) { obCandleIdx = j; break; }
     }
   else // bearish break -> last up candle
     {
      for(int j=b-1; j>=start; j--)
         if(m_close[j] > m_open[j]) { obCandleIdx = j; break; }
     }
   if(obCandleIdx < 0) return;

   m_nObs++;
   ArrayResize(m_obs, m_nObs);
   int o = m_nObs - 1;
   m_obs[o].source_bar = obCandleIdx;
   m_obs[o].open = m_open[obCandleIdx];
   m_obs[o].high = m_high[obCandleIdx];
   m_obs[o].low = m_low[obCandleIdx];
   m_obs[o].close = m_close[obCandleIdx];
   m_obs[o].direction = ev.direction;
   m_obs[o].disp_atr = ev.disp_atr;
   m_obs[o].creation_bar = b;
   m_obs[o].conf_bar = b;
   m_obs[o].upper = m_high[obCandleIdx];
   m_obs[o].lower = m_low[obCandleIdx];
   m_obs[o].mid = (m_high[obCandleIdx] + m_low[obCandleIdx]) / 2.0;
   m_obs[o].invalidated = false;
   m_obs[o].inv_bar = m_nBars; // will be set if invalidated
   m_obs[o].mitigation_count = 0;
   m_obs[o].freshness = "fresh";
   m_obs[o].lifecycle = "fresh";
   m_obs[o].deepest_pen = 0.0;
   m_obs[o].quality = MathMin(1.0, ev.disp_atr / (V38_2_CHOCH_MIN_ATR_MULT * 3));

   // Track mitigation forward (only new bars since last update)
   int ageLimit = V38_2_OB_MAX_AGE_BARS;
   double zoneHigh = m_obs[o].high;
   double zoneLow = m_obs[o].low;
   double depth = zoneHigh - zoneLow;
   if(depth <= 0)
     { m_obs[o].lifecycle = "invalidated"; m_obs[o].invalidated = true; return; }

   bool firstTouch = true;
   double deepest = 0.0;
   for(int bb = m_obs[o].conf_bar + 1;
       bb < MathMin(m_nBars, m_obs[o].conf_bar + 1 + ageLimit); bb++)
     {
      double bh = m_high[bb], bl = m_low[bb], bc = m_close[bb];
      bool entered = (bh >= zoneLow && bl <= zoneHigh);
      if(entered)
        {
         if(firstTouch)
           { m_obs[o].freshness = "touched"; m_obs[o].lifecycle = "touched"; firstTouch = false; }
         m_obs[o].mitigation_count++;
         double pen;
         if(m_obs[o].direction == 1) pen = MathMax(0.0, bh - zoneLow) / depth;
         else pen = MathMax(0.0, zoneHigh - bl) / depth;
         deepest = MathMax(deepest, pen);
         if(V38_2_OB_CLOSE_THROUGH_INV)
           {
            if(m_obs[o].direction == 1 && bc < zoneLow)
              { m_obs[o].lifecycle = "fully_consumed"; break; }
            if(m_obs[o].direction == -1 && bc > zoneHigh)
              { m_obs[o].lifecycle = "fully_consumed"; break; }
           }
         if(deepest > 0.5 && m_obs[o].lifecycle != "fully_consumed")
            m_obs[o].lifecycle = "partially_consumed";
        }
      // invalidation
      if(m_obs[o].direction == 1 && bc > zoneHigh)
        { m_obs[o].lifecycle = "invalidated"; m_obs[o].invalidated = true;
          m_obs[o].inv_bar = bb; break; }
      if(m_obs[o].direction == -1 && bc < zoneLow)
        { m_obs[o].lifecycle = "invalidated"; m_obs[o].invalidated = true;
          m_obs[o].inv_bar = bb; break; }
     }
   m_obs[o].deepest_pen = deepest;
   if(!m_obs[o].invalidated && m_obs[o].mitigation_count == 0 &&
      StringCompare(m_obs[o].lifecycle, "fully_consumed") != 0)
      m_obs[o].freshness = "stale";

   // Also update existing OBs for new mitigation bars
   for(int oi=0; oi<m_nObs-1; oi++)
     {
      if(m_obs[oi].invalidated) continue;
      // Check the latest bar only for mitigation updates
      int bb = m_nBars - 1;
      if(bb <= m_obs[oi].conf_bar) continue;
      if(bb > m_obs[oi].conf_bar + V38_2_OB_MAX_AGE_BARS) continue;
      double bh = m_high[bb], bl = m_low[bb], bc = m_close[bb];
      double zh = m_obs[oi].high, zl = m_obs[oi].low;
      double d = zh - zl;
      if(d <= 0) continue;
      bool entered = (bh >= zl && bl <= zh);
      if(entered)
        {
         if(StringCompare(m_obs[oi].freshness, "fresh") == 0)
           { m_obs[oi].freshness = "touched"; m_obs[oi].lifecycle = "touched"; }
         m_obs[oi].mitigation_count++;
         double pen;
         if(m_obs[oi].direction == 1) pen = MathMax(0.0, bh - zl) / d;
         else pen = MathMax(0.0, zh - bl) / d;
         m_obs[oi].deepest_pen = MathMax(m_obs[oi].deepest_pen, pen);
         if(pen > 0.5 && StringCompare(m_obs[oi].lifecycle, "fully_consumed") != 0)
            m_obs[oi].lifecycle = "partially_consumed";
        }
      if(V38_2_OB_CLOSE_THROUGH_INV)
        {
         if(m_obs[oi].direction == 1 && bc < zl)
           { m_obs[oi].lifecycle = "fully_consumed"; }
         if(m_obs[oi].direction == -1 && bc > zh)
           { m_obs[oi].lifecycle = "fully_consumed"; }
        }
      if(m_obs[oi].direction == 1 && bc > zh)
        { m_obs[oi].lifecycle = "invalidated"; m_obs[oi].invalidated = true;
          m_obs[oi].inv_bar = bb; }
      if(m_obs[oi].direction == -1 && bc < zl)
        { m_obs[oi].lifecycle = "invalidated"; m_obs[oi].invalidated = true;
          m_obs[oi].inv_bar = bb; }
     }
  }

//+------------------------------------------------------------------+
//| FVG detection (mirrors FVGEngine.build)                          |
//+------------------------------------------------------------------+
void CV38_2StructureEngine::DetectFVGs()
  {
   if(m_nBars < 3) return;
   int i = m_nBars - 1; // check latest bar as potential FVG creation
   if(i < 2) return;

   // Check if already processed
   for(int f=0; f<m_nFvgs; f++)
      if(m_fvgs[f].creation_bar == i) return;

   double a = ComputeATRVal(i);
   double minSize = V38_2_FVG_MIN_SIZE_ATR * a;

   // Bullish: low[i] > high[i-2]
   if(m_low[i] > m_high[i-2])
     {
      double size = m_low[i] - m_high[i-2];
      if(size >= minSize)
        {
         m_nFvgs++;
         ArrayResize(m_fvgs, m_nFvgs);
         int f = m_nFvgs - 1;
         m_fvgs[f].direction = 1;
         m_fvgs[f].upper = m_low[i];
         m_fvgs[f].lower = m_high[i-2];
         m_fvgs[f].mid = (m_low[i] + m_high[i-2]) / 2.0;
         m_fvgs[f].size_atr = size / a;
         m_fvgs[f].creation_bar = i;
         m_fvgs[f].conf_bar = i;
         m_fvgs[f].invalidated = false;
         m_fvgs[f].inv_bar = m_nBars;
         m_fvgs[f].lifecycle = "open";
         m_fvgs[f].fill_pct = 0.0;
         // Track fill forward
         for(int bb=i+1; bb<m_nBars; bb++)
           {
            double bh=m_high[bb], bl=m_low[bb], bc=m_close[bb];
            bool entered = (bh >= m_fvgs[f].lower && bl <= m_fvgs[f].upper);
            if(entered)
              {
               if(StringCompare(m_fvgs[f].lifecycle, "open") == 0)
                  m_fvgs[f].lifecycle = "partially_filled";
               double filled;
               if(m_fvgs[f].direction == 1)
                  filled = (bl < m_fvgs[f].upper) ? (m_fvgs[f].upper - MathMax(m_fvgs[f].lower, bl)) : 0.0;
               else
                  filled = (bh > m_fvgs[f].lower) ? (MathMin(m_fvgs[f].upper, bh) - m_fvgs[f].lower) : 0.0;
               double pct = MathMax(0.0, MathMin(1.0, filled / (m_fvgs[f].upper - m_fvgs[f].lower)));
               m_fvgs[f].fill_pct = MathMax(m_fvgs[f].fill_pct, pct);
               if(pct >= 1.0) m_fvgs[f].lifecycle = "fully_filled";
               if(m_fvgs[f].direction == 1 && bc < m_fvgs[f].lower)
                 { m_fvgs[f].lifecycle = "invalidated"; m_fvgs[f].invalidated = true; m_fvgs[f].inv_bar = bb; break; }
               if(m_fvgs[f].direction == -1 && bc > m_fvgs[f].upper)
                 { m_fvgs[f].lifecycle = "invalidated"; m_fvgs[f].invalidated = true; m_fvgs[f].inv_bar = bb; break; }
              }
           }
        }
     }
   // Bearish: high[i] < low[i-2]
   else if(m_high[i] < m_low[i-2])
     {
      double size = m_low[i-2] - m_high[i];
      if(size >= minSize)
        {
         m_nFvgs++;
         ArrayResize(m_fvgs, m_nFvgs);
         int f = m_nFvgs - 1;
         m_fvgs[f].direction = -1;
         m_fvgs[f].upper = m_low[i-2];
         m_fvgs[f].lower = m_high[i];
         m_fvgs[f].mid = (m_low[i-2] + m_high[i]) / 2.0;
         m_fvgs[f].size_atr = size / a;
         m_fvgs[f].creation_bar = i;
         m_fvgs[f].conf_bar = i;
         m_fvgs[f].invalidated = false;
         m_fvgs[f].inv_bar = m_nBars;
         m_fvgs[f].lifecycle = "open";
         m_fvgs[f].fill_pct = 0.0;
         for(int bb=i+1; bb<m_nBars; bb++)
           {
            double bh=m_high[bb], bl=m_low[bb], bc=m_close[bb];
            bool entered = (bh >= m_fvgs[f].lower && bl <= m_fvgs[f].upper);
            if(entered)
              {
               if(StringCompare(m_fvgs[f].lifecycle, "open") == 0)
                  m_fvgs[f].lifecycle = "partially_filled";
               double filled;
               if(m_fvgs[f].direction == 1)
                  filled = (bl < m_fvgs[f].upper) ? (m_fvgs[f].upper - MathMax(m_fvgs[f].lower, bl)) : 0.0;
               else
                  filled = (bh > m_fvgs[f].lower) ? (MathMin(m_fvgs[f].upper, bh) - m_fvgs[f].lower) : 0.0;
               double pct = MathMax(0.0, MathMin(1.0, filled / (m_fvgs[f].upper - m_fvgs[f].lower)));
               m_fvgs[f].fill_pct = MathMax(m_fvgs[f].fill_pct, pct);
               if(pct >= 1.0) m_fvgs[f].lifecycle = "fully_filled";
               if(m_fvgs[f].direction == 1 && bc < m_fvgs[f].lower)
                 { m_fvgs[f].lifecycle = "invalidated"; m_fvgs[f].invalidated = true; m_fvgs[f].inv_bar = bb; break; }
               if(m_fvgs[f].direction == -1 && bc > m_fvgs[f].upper)
                 { m_fvgs[f].lifecycle = "invalidated"; m_fvgs[f].invalidated = true; m_fvgs[f].inv_bar = bb; break; }
              }
           }
        }
     }

   // Update existing FVGs with latest bar
   int bb = m_nBars - 1;
   for(int fi=0; fi<m_nFvgs-1; fi++)
     {
      if(m_fvgs[fi].invalidated) continue;
      if(bb <= m_fvgs[fi].creation_bar) continue;
      double bh=m_high[bb], bl=m_low[bb], bc=m_close[bb];
      bool entered = (bh >= m_fvgs[fi].lower && bl <= m_fvgs[fi].upper);
      if(entered)
        {
         if(StringCompare(m_fvgs[fi].lifecycle, "open") == 0)
            m_fvgs[fi].lifecycle = "partially_filled";
         double span = m_fvgs[fi].upper - m_fvgs[fi].lower;
         double filled;
         if(m_fvgs[fi].direction == 1)
            filled = (bl < m_fvgs[fi].upper) ? (m_fvgs[fi].upper - MathMax(m_fvgs[fi].lower, bl)) : 0.0;
         else
            filled = (bh > m_fvgs[fi].lower) ? (MathMin(m_fvgs[fi].upper, bh) - m_fvgs[fi].lower) : 0.0;
         if(span > 0)
           {
            double pct = MathMax(0.0, MathMin(1.0, filled / span));
            m_fvgs[fi].fill_pct = MathMax(m_fvgs[fi].fill_pct, pct);
            if(pct >= 1.0) m_fvgs[fi].lifecycle = "fully_filled";
           }
        }
      if(m_fvgs[fi].direction == 1 && bc < m_fvgs[fi].lower)
        { m_fvgs[fi].lifecycle = "invalidated"; m_fvgs[fi].invalidated = true; m_fvgs[fi].inv_bar = bb; }
      if(m_fvgs[fi].direction == -1 && bc > m_fvgs[fi].upper)
        { m_fvgs[fi].lifecycle = "invalidated"; m_fvgs[fi].invalidated = true; m_fvgs[fi].inv_bar = bb; }
     }
  }

//+------------------------------------------------------------------+
//| Liquidity detection (mirrors LiquidityEngine.build)              |
//+------------------------------------------------------------------+
void CV38_2StructureEngine::DetectLiquidity()
  {
   // Build pools from confirmed swings (cluster same-polarity)
   // For incremental update, check if latest confirmed swing creates a new pool
   if(m_nSwings == 0) return;
   int latestSwingIdx = m_nSwings - 1;
   V38_2Swing sw = m_swings[latestSwingIdx];
   if(sw.conf_bar > m_nBars - 1) return; // not yet confirmed

   // Check if we already have a pool for this swing
   for(int p=0; p<m_nPools; p++)
      if(m_pools[p].conf_bar == sw.conf_bar && m_pools[p].type == sw.kind) return;

   // Cluster: find nearby same-polarity swings
   double clusterAtr = V38_2_LIQ_CLUSTER_ATR;
   double a = ComputeATRVal(sw.conf_bar);
   double tol = clusterAtr * a;

   // Find all same-kind swings within tolerance
   int members[];
   int nMembers = 0;
   ArrayResize(members, m_nSwings);
   for(int s=0; s<m_nSwings; s++)
     {
      if(m_swings[s].kind == sw.kind && MathAbs(m_swings[s].price - sw.price) <= tol)
        { members[nMembers] = s; nMembers++; }
     }
   if(nMembers == 0) return;

   double sumPrice = 0;
   int maxConfBar = 0;
   for(int m=0; m<nMembers; m++)
     {
      sumPrice += m_swings[members[m]].price;
      if(m_swings[members[m]].conf_bar > maxConfBar)
         maxConfBar = m_swings[members[m]].conf_bar;
     }
   double poolPrice = sumPrice / nMembers;

   // Check if this pool already exists
   for(int p=0; p<m_nPools; p++)
     {
      if(m_pools[p].type == sw.kind && MathAbs(m_pools[p].price - poolPrice) < tol)
         return; // already clustered
     }

   m_nPools++;
   ArrayResize(m_pools, m_nPools);
   int p = m_nPools - 1;
   m_pools[p].type = sw.kind;
   m_pools[p].price = poolPrice;
   m_pools[p].creation_bar = m_swings[members[0]].bar_index;
   m_pools[p].conf_bar = maxConfBar;
   m_pools[p].touches = nMembers;
   m_pools[p].strength = MathMin(1.0, (double)nMembers / 4.0);
   m_pools[p].invalidated = false;
   m_pools[p].swept = false;
   m_pools[p].sweep_bar = -1;
   m_pools[p].sweep_depth_atr = 0.0;
   m_pools[p].post_sweep_atr = 0.0;

   // Detect sweeps for this pool
   for(int bb=m_pools[p].conf_bar+1; bb<m_nBars; bb++)
     {
      if(m_pools[p].type == 1 && m_high[bb] > m_pools[p].price && m_close[bb] < m_pools[p].price)
        {
         m_pools[p].swept = true;
         m_pools[p].sweep_bar = bb;
         double aa = ComputeATRVal(bb);
         m_pools[p].sweep_depth_atr = (m_high[bb] - m_pools[p].price) / aa;
         int end = MathMin(m_nBars, bb + 11);
         double mfe = 0;
         for(int k=bb; k<end; k++)
            mfe = MathMin(mfe, m_low[k] - m_pools[p].price);
         m_pools[p].post_sweep_atr = (-mfe) / aa;
         break;
        }
      if(m_pools[p].type == -1 && m_low[bb] < m_pools[p].price && m_close[bb] > m_pools[p].price)
        {
         m_pools[p].swept = true;
         m_pools[p].sweep_bar = bb;
         double aa = ComputeATRVal(bb);
         m_pools[p].sweep_depth_atr = (m_pools[p].price - m_low[bb]) / aa;
         int end = MathMin(m_nBars, bb + 11);
         double mfe = 0;
         for(int k=bb; k<end; k++)
            mfe = MathMax(mfe, m_high[k] - m_pools[p].price);
         m_pools[p].post_sweep_atr = mfe / aa;
         break;
        }
     }

   // Update existing pools for new sweeps on latest bar
   int latestBar = m_nBars - 1;
   for(int pi=0; pi<m_nPools-1; pi++)
     {
      if(m_pools[pi].swept) continue;
      if(latestBar <= m_pools[pi].conf_bar) continue;
      if(m_pools[pi].type == 1 && m_high[latestBar] > m_pools[pi].price && m_close[latestBar] < m_pools[pi].price)
        {
         m_pools[pi].swept = true;
         m_pools[pi].sweep_bar = latestBar;
         double aa = ComputeATRVal(latestBar);
         m_pools[pi].sweep_depth_atr = (m_high[latestBar] - m_pools[pi].price) / aa;
         int end = MathMin(m_nBars, latestBar + 11);
         double mfe = 0;
         for(int k=latestBar; k<end; k++)
            mfe = MathMin(mfe, m_low[k] - m_pools[pi].price);
         m_pools[pi].post_sweep_atr = (-mfe) / aa;
        }
      if(m_pools[pi].type == -1 && m_low[latestBar] < m_pools[pi].price && m_close[latestBar] > m_pools[pi].price)
        {
         m_pools[pi].swept = true;
         m_pools[pi].sweep_bar = latestBar;
         double aa = ComputeATRVal(latestBar);
         m_pools[pi].sweep_depth_atr = (m_pools[pi].price - m_low[latestBar]) / aa;
         int end = MathMin(m_nBars, latestBar + 11);
         double mfe = 0;
         for(int k=latestBar; k<end; k++)
            mfe = MathMax(mfe, m_high[k] - m_pools[pi].price);
         m_pools[pi].post_sweep_atr = mfe / aa;
        }
     }

   // Equal levels: swings of same polarity within ATR tolerance
   // Check if latest swing forms an equal level with a previous one
   double eqTol = V38_2_EQH_EQL_ATR_TOL * a;
   for(int s=0; s<m_nSwings-1; s++)
     {
      if(m_swings[s].kind != sw.kind) continue;
      if(MathAbs(m_swings[s].price - sw.price) <= eqTol)
        {
         // Check if we already have this equal level
         bool exists = false;
         for(int e=0; e<m_nEqs; e++)
            if(m_eqs[e].conf_bar == sw.conf_bar)
              { exists = true; break; }
         if(!exists)
           {
            m_nEqs++;
            ArrayResize(m_eqs, m_nEqs);
            m_eqs[m_nEqs-1].conf_bar = sw.conf_bar;
            m_eqs[m_nEqs-1].type = sw.kind;
           }
        }
     }

   // Inducements: internal swings within legs
   if(!sw.external && m_nLegs > 0)
     {
      for(int l=0; l<m_nLegs; l++)
        {
         if(sw.conf_bar >= m_legs[l].start_bar && sw.conf_bar <= m_legs[l].end_bar)
           {
            bool exists = false;
            for(int ind=0; ind<m_nInds; ind++)
               if(m_inds[ind].conf_bar == sw.conf_bar)
                 { exists = true; break; }
            if(!exists)
              {
               m_nInds++;
               ArrayResize(m_inds, m_nInds);
               m_inds[m_nInds-1].conf_bar = sw.conf_bar;
              }
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Premium/Discount detection (mirrors PremiumDiscountEngine)      |
//+------------------------------------------------------------------+
void CV38_2StructureEngine::DetectPD()
  {
   // PD is computed on-the-fly in the query methods using legs
   // No precomputation needed here
  }

//+------------------------------------------------------------------+
//| Precompute per-bar query arrays (mirrors StructureIndex)         |
//+------------------------------------------------------------------+
void CV38_2StructureEngine::PrecomputeQueries()
  {
   if(m_nBars == 0) return;
   int n = m_nBars;

   // Regime array
   ArrayResize(m_regArr, n);
   for(int b=0; b<n; b++)
     {
      // Find regime as of bar b: last CHOCH before b
      int reg = 1; // neutral
      for(int e=0; e<m_nEvents; e++)
        {
         if(m_events[e].conf_bar <= b && m_events[e].event_type == "CHOCH")
           {
            if(m_events[e].direction == 1) reg = 2; // bullish
            else reg = 0; // bearish
           }
        }
      m_regArr[b] = reg;
     }

   // Protected extents
   ArrayResize(m_protMaxHigh, n);
   ArrayResize(m_protMinLow, n);
   double runMaxH = -DBL_MAX, runMinL = DBL_MAX;
   for(int b=0; b<n; b++)
     {
      for(int p=0; p<m_nProts; p++)
        {
         if(m_prots[p].conf_bar <= b && m_prots[p].status == 0)
           {
            if(m_prots[p].kind == 1 && m_prots[p].price > runMaxH) runMaxH = m_prots[p].price;
            if(m_prots[p].kind == -1 && m_prots[p].price < runMinL) runMinL = m_prots[p].price;
           }
        }
      m_protMaxHigh[b] = runMaxH;
      m_protMinLow[b] = runMinL;
     }

   // OB direction flags (with and without lifecycle filter)
   ArrayResize(m_hasObBull, n); ArrayResize(m_hasObBear, n);
   ArrayResize(m_hasObAnyBull, n); ArrayResize(m_hasObAnyBear, n);
   bool fb=false, fbr=false, fab=false, fabr=false;
   for(int b=0; b<n; b++)
     {
      for(int o=0; o<m_nObs; o++)
        {
         if(m_obs[o].conf_bar <= b)
           {
            bool validLC = (StringCompare(m_obs[o].lifecycle, "fresh")==0 ||
                            StringCompare(m_obs[o].lifecycle, "touched")==0 ||
                            StringCompare(m_obs[o].lifecycle, "partially_consumed")==0);
            if(!m_obs[o].invalidated && validLC)
              {
               if(m_obs[o].direction == 1) fb = true;
               if(m_obs[o].direction == -1) fbr = true;
              }
            if(!m_obs[o].invalidated)
              {
               if(m_obs[o].direction == 1) fab = true;
               if(m_obs[o].direction == -1) fabr = true;
              }
           }
        }
      m_hasObBull[b] = fb; m_hasObBear[b] = fbr;
      m_hasObAnyBull[b] = fab; m_hasObAnyBear[b] = fabr;
     }

   // FVG direction flags
   ArrayResize(m_hasFvgBull, n); ArrayResize(m_hasFvgBear, n);
   bool fvb=false, fvbr=false;
   for(int b=0; b<n; b++)
     {
      for(int f=0; f<m_nFvgs; f++)
        {
         if(m_fvgs[f].conf_bar <= b && !m_fvgs[f].invalidated &&
            (StringCompare(m_fvgs[f].lifecycle, "open")==0 ||
             StringCompare(m_fvgs[f].lifecycle, "partially_filled")==0))
           {
            if(m_fvgs[f].direction == 1) fvb = true;
            if(m_fvgs[f].direction == -1) fvbr = true;
           }
        }
      m_hasFvgBull[b] = fvb; m_hasFvgBear[b] = fvbr;
     }

   // Swept pool flag
   ArrayResize(m_hasSweptPool, n);
   bool fsp = false;
   for(int b=0; b<n; b++)
     {
      for(int p=0; p<m_nPools; p++)
         if(m_pools[p].conf_bar <= b && m_pools[p].swept) { fsp = true; break; }
      m_hasSweptPool[b] = fsp;
     }

   // Swept recent (within last 10 bars)
   ArrayResize(m_sweptRecent, n);
   ArrayResize(m_sweepDepth, n);
   ArrayResize(m_sweepReaction, n);
   for(int b=0; b<n; b++)
     {
      bool recent = false;
      double depth = 0, react = 0;
      int lastSweepBar = -1;
      for(int p=0; p<m_nPools; p++)
        {
         if(m_pools[p].swept && m_pools[p].sweep_bar >= 0 &&
            m_pools[p].sweep_bar <= b && m_pools[p].sweep_bar >= b - V38_2_POOL_SWEEP_LOOKBACK)
           {
            recent = true;
            if(m_pools[p].sweep_bar > lastSweepBar)
              { lastSweepBar = m_pools[p].sweep_bar;
                depth = m_pools[p].sweep_depth_atr;
                react = m_pools[p].post_sweep_atr; }
           }
        }
      m_sweptRecent[b] = recent;
      m_sweepDepth[b] = depth;
      m_sweepReaction[b] = react;
     }

   // EQ/EQL present (within 100 bars)
   ArrayResize(m_eqPresent, n);
   for(int b=0; b<n; b++)
     {
      bool present = false;
      for(int e=0; e<m_nEqs; e++)
         if(m_eqs[e].conf_bar <= b && b - m_eqs[e].conf_bar <= V38_2_EQ_LOOKBACK)
           { present = true; break; }
      m_eqPresent[b] = present;
     }

   // Inducement present (within 50 bars)
   ArrayResize(m_indPresent, n);
   for(int b=0; b<n; b++)
     {
      bool present = false;
      for(int ind=0; ind<m_nInds; ind++)
         if(m_inds[ind].conf_bar <= b && b - m_inds[ind].conf_bar <= V38_2_IND_LOOKBACK)
           { present = true; break; }
      m_indPresent[b] = present;
     }

   // Last BOS/CHOCH event per bar
   ArrayResize(m_lastBcQuality, n);
   ArrayResize(m_lastEvDir, n);
   ArrayResize(m_lastEvDisp, n);
   ArrayResize(m_lastEvAge, n);
   ArrayResize(m_nBosLast50, n);
   ArrayResize(m_nChochLast50, n);
   ArrayResize(m_last3ChochBull, n);
   ArrayResize(m_last3ChochBear, n);
   for(int b=0; b<n; b++)
     {
      double lastQ = 0; int lastEvIdx = -1;
      int nBos = 0, nChoch = 0;
      for(int e=0; e<m_nEvents; e++)
        {
         if(m_events[e].conf_bar <= b)
           {
            if(m_events[e].event_type == "BOS" || m_events[e].event_type == "CHOCH")
              { lastQ = m_events[e].quality; lastEvIdx = e; }
            // Count last 50 events
            if(e >= MathMax(0, m_nEvents - 50)) // simplified: last 50 in array
              {
               if(m_events[e].event_type == "BOS") nBos++;
               if(m_events[e].event_type == "CHOCH") nChoch++;
              }
           }
        }
      m_lastBcQuality[b] = lastQ;
      if(lastEvIdx >= 0)
        {
         m_lastEvDir[b] = (m_events[lastEvIdx].direction == 1) ? DIR_ENC_BULL :
                          ((m_events[lastEvIdx].direction == -1) ? DIR_ENC_BEAR : DIR_ENC_NEUT);
         m_lastEvDisp[b] = m_events[lastEvIdx].disp_atr;
         m_lastEvAge[b] = (double)(b - m_events[lastEvIdx].conf_bar);
        }
      else
        { m_lastEvDir[b] = 0; m_lastEvDisp[b] = 0; m_lastEvAge[b] = -1; }
      m_nBosLast50[b] = nBos;
      m_nChochLast50[b] = nChoch;

      // Last 3 CHOCH check
      bool last3Bull = false, last3Bear = false;
      int count = 0;
      for(int e=m_nEvents-1; e>=0 && count<3; e--)
        {
         if(m_events[e].conf_bar <= b)
           {
            if(m_events[e].event_type == "CHOCH")
              {
               if(m_events[e].direction == 1) last3Bull = true;
               if(m_events[e].direction == -1) last3Bear = true;
              }
            count++;
           }
        }
      m_last3ChochBull[b] = last3Bull;
      m_last3ChochBear[b] = last3Bear;
     }

   // Pool extents (max/min active pool price per bar)
   ArrayResize(m_poolMaxPrice, n);
   ArrayResize(m_poolMinPrice, n);
   double runMaxP = -DBL_MAX, runMinP = DBL_MAX;
   for(int b=0; b<n; b++)
     {
      for(int p=0; p<m_nPools; p++)
        {
         if(m_pools[p].conf_bar <= b && !m_pools[p].invalidated)
           {
            if(m_pools[p].price > runMaxP) runMaxP = m_pools[p].price;
            if(m_pools[p].price < runMinP) runMinP = m_pools[p].price;
           }
        }
      m_poolMaxPrice[b] = runMaxP;
      m_poolMinPrice[b] = runMinP;
     }
  }

//+------------------------------------------------------------------+
//| Feature engine method overrides                                  |
//+------------------------------------------------------------------+
int CV38_2StructureEngine::RegimeAt(int bar)
  {
   if(bar < 0 || bar >= m_nBars) return 1;
   return m_regArr[bar];
  }

string CV38_2StructureEngine::RegimeStrAt(int bar)
  {
   int r = RegimeAt(bar);
   if(r == 2) return "bullish";
   if(r == 0) return "bearish";
   return "neutral";
  }

int CV38_2StructureEngine::HTFBarForLTF(int ltfBar)
  {
   if(m_htf == NULL) return 0;
   // Find the HTF bar whose ts <= LTF bar ts
   if(ltfBar < 0 || ltfBar >= m_nBars) return 0;
   datetime target = m_ts[ltfBar];
   int n = m_htf.NBars();
   // Binary search: last HTF bar with ts <= target
   int lo = 0, hi = n - 1, result = 0;
   while(lo <= hi)
     {
      int mid = (lo + hi) / 2;
      if(m_htf.TsAt(mid) <= target) { result = mid; lo = mid + 1; }
      else hi = mid - 1;
     }
   return result;
  }

double CV38_2StructureEngine::HTFRegimeEnc(int htfBar)
  {
   if(m_htf == NULL) return REG_ENC_NEUT;
   // htfBar here is actually the LTF bar index; convert to HTF bar
   int hBar = HTFBarForLTF(htfBar);
   int r = m_htf.RegimeAt(hBar);
   return (r == 2) ? REG_ENC_BULL : ((r == 0) ? REG_ENC_BEAR : REG_ENC_NEUT);
  }

double CV38_2StructureEngine::LTFRegimeEnc(int ltfBar)
  {
   int r = RegimeAt(ltfBar);
   return (r == 2) ? REG_ENC_BULL : ((r == 0) ? REG_ENC_BEAR : REG_ENC_NEUT);
  }

double CV38_2StructureEngine::BOSCountRecent(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars) return 0;
   return (double)m_nBosLast50[ltfBar];
  }

double CV38_2StructureEngine::CHOCHCountRecent(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars) return 0;
   return (double)m_nChochLast50[ltfBar];
  }

double CV38_2StructureEngine::LastEventDirEnc(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars) return 0;
   return m_lastEvDir[ltfBar];
  }

double CV38_2StructureEngine::LastEventDispATR(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars) return 0;
   return m_lastEvDisp[ltfBar];
  }

double CV38_2StructureEngine::LastEventAgeBars(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars) return -1;
   return m_lastEvAge[ltfBar];
  }

double CV38_2StructureEngine::ProtectedHigh(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars) return 0;
   double h = m_protMaxHigh[ltfBar];
   return (h > -DBL_MAX) ? h : 0.0;
  }

double CV38_2StructureEngine::ProtectedLow(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars) return 0;
   double l = m_protMinLow[ltfBar];
   return (l < DBL_MAX) ? l : 0.0;
  }

double CV38_2StructureEngine::MinProtectedLow(int bar, double fallback)
  {
   if(bar < 0 || bar >= m_nBars) return fallback;
   double v = m_protMinLow[bar];
   return (v < DBL_MAX) ? v : fallback;
  }

double CV38_2StructureEngine::MaxProtectedHigh(int bar, double fallback)
  {
   if(bar < 0 || bar >= m_nBars) return fallback;
   double v = m_protMaxHigh[bar];
   return (v > -DBL_MAX) ? v : fallback;
  }

double CV38_2StructureEngine::MultiLegAligned(int ltfBar)
  {
   // 1.0 if HTF regime == LTF regime and both non-neutral
   double htf = HTFRegimeEnc(ltfBar);
   double ltf = LTFRegimeEnc(ltfBar);
   return (htf == ltf && ltf != REG_ENC_NEUT) ? 1.0 : 0.0;
  }

double CV38_2StructureEngine::LegExtensionATR(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars || m_nLegs == 0) return 0;
   // Find latest confirmed leg
   double legStart = 0;
   for(int l=m_nLegs-1; l>=0; l--)
     {
      if(m_legs[l].conf_bar <= ltfBar)
        { legStart = m_legs[l].start_price; break; }
     }
   if(legStart == 0) return 0;
   double ext = MathAbs(m_close[ltfBar] - legStart);
   double a = ComputeATRVal(ltfBar);
   return ext / (a > 0 ? a : 1.0);
  }

double CV38_2StructureEngine::StructureStrength(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars) return 0;
   // This is called from BuildVector with a direction; we compute it
   // generically using the last BOS/CHOCH quality + flags
   double score = 0.4 * m_lastBcQuality[ltfBar];
   if(m_hasObAnyBull[ltfBar] || m_hasObAnyBear[ltfBar]) score += 0.3;
   if(m_hasFvgBull[ltfBar] || m_hasFvgBear[ltfBar]) score += 0.2;
   if(m_hasSweptPool[ltfBar]) score += 0.1;
   return MathMin(1.0, score);
  }

// Override StructureStrength for direction-specific
double CV38_2StructureEngine::NearestLiquidityDistATR(int ltfBar, double price, double atrVal)
  {
   if(m_nPools == 0 || ltfBar >= m_nBars) return 0;
   double minDist = DBL_MAX;
   for(int p=0; p<m_nPools; p++)
     {
      if(m_pools[p].conf_bar <= ltfBar && !m_pools[p].invalidated)
        {
         double d = MathAbs(m_pools[p].price - price);
         if(d < minDist) minDist = d;
        }
     }
   if(minDist == DBL_MAX) return 0;
   return minDist / (atrVal > 0 ? atrVal : 1.0);
  }

double CV38_2StructureEngine::NearestLiquiditySideEnc(int ltfBar, double price, double atrVal)
  {
   if(m_nPools == 0 || ltfBar >= m_nBars) return 0;
   double minDist = DBL_MAX;
   int nearestType = 0;
   double nearestPrice = price;
   for(int p=0; p<m_nPools; p++)
     {
      if(m_pools[p].conf_bar <= ltfBar && !m_pools[p].invalidated)
        {
         double d = MathAbs(m_pools[p].price - price);
         if(d < minDist) { minDist = d; nearestType = m_pools[p].type;
                            nearestPrice = m_pools[p].price; }
        }
     }
   if(minDist == DBL_MAX) return 0;
   double side;
   if(nearestType == 1 && nearestPrice < price) side = -1.0;
   else if(nearestType == -1 && nearestPrice > price) side = 1.0;
   else side = (nearestPrice >= price) ? 1.0 : -1.0;
   return side;
  }

double CV38_2StructureEngine::LiquiditySwept(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars) return 0;
   return m_sweptRecent[ltfBar] ? 1.0 : 0.0;
  }

double CV38_2StructureEngine::SweepDepthATR(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars) return 0;
   return m_sweepDepth[ltfBar];
  }

double CV38_2StructureEngine::PostSweepReactionATR(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars) return 0;
   return m_sweepReaction[ltfBar];
  }

double CV38_2StructureEngine::EQHEQLPresent(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars) return 0;
   return m_eqPresent[ltfBar] ? 1.0 : 0.0;
  }

double CV38_2StructureEngine::InducementPresent(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars) return 0;
   return m_indPresent[ltfBar] ? 1.0 : 0.0;
  }

//--- OB queries ---
double CV38_2StructureEngine::NearestOB(int bar, double price, double atrVal, int &outIdx)
  {
   outIdx = -1;
   if(m_nObs == 0) return 0;
   double minDist = DBL_MAX;
   for(int o=0; o<m_nObs; o++)
     {
      if(m_obs[o].invalidated) continue;
      if(m_obs[o].conf_bar > bar) continue;
      if(m_obs[o].inv_bar <= bar) continue;
      string lc = m_obs[o].lifecycle;
      if(StringCompare(lc, "fresh") != 0 && StringCompare(lc, "touched") != 0 &&
         StringCompare(lc, "partially_consumed") != 0) continue;
      double dist;
      if(price < m_obs[o].lower) dist = m_obs[o].lower - price;
      else if(price > m_obs[o].upper) dist = price - m_obs[o].upper;
      else dist = 0;
      if(dist < minDist) { minDist = dist; outIdx = o; }
     }
   return minDist;
  }

double CV38_2StructureEngine::OBPresent(int ltfBar)
  {
   int idx;
   double price = (ltfBar >= 0 && ltfBar < m_nBars) ? m_close[ltfBar] : 0;
   double atrVal = ComputeATRVal(ltfBar);
   NearestOB(ltfBar, price, atrVal, idx);
   return (idx >= 0) ? 1.0 : 0.0;
  }

double CV38_2StructureEngine::OBDirectionEnc(int ltfBar)
  {
   int idx;
   double price = (ltfBar >= 0 && ltfBar < m_nBars) ? m_close[ltfBar] : 0;
   double atrVal = ComputeATRVal(ltfBar);
   NearestOB(ltfBar, price, atrVal, idx);
   if(idx < 0) return 0;
   return (m_obs[idx].direction == 1) ? DIR_ENC_BULL :
          ((m_obs[idx].direction == -1) ? DIR_ENC_BEAR : DIR_ENC_NEUT);
  }

double CV38_2StructureEngine::OBStrength(int ltfBar)
  {
   int idx;
   double price = (ltfBar >= 0 && ltfBar < m_nBars) ? m_close[ltfBar] : 0;
   double atrVal = ComputeATRVal(ltfBar);
   NearestOB(ltfBar, price, atrVal, idx);
   return (idx >= 0) ? m_obs[idx].quality : 0.0;
  }

double CV38_2StructureEngine::OBDistanceATR(int ltfBar, double price, double atrVal)
  {
   int idx;
   NearestOB(ltfBar, price, atrVal, idx);
   if(idx < 0) return 0;
   double d;
   if(price < m_obs[idx].lower) d = m_obs[idx].lower - price;
   else if(price > m_obs[idx].upper) d = price - m_obs[idx].upper;
   else d = 0;
   return d / (atrVal > 0 ? atrVal : 1.0);
  }

double CV38_2StructureEngine::OBAgeBars(int ltfBar)
  {
   int idx;
   double price = (ltfBar >= 0 && ltfBar < m_nBars) ? m_close[ltfBar] : 0;
   double atrVal = ComputeATRVal(ltfBar);
   NearestOB(ltfBar, price, atrVal, idx);
   return (idx >= 0) ? (double)(ltfBar - m_obs[idx].conf_bar) : 0.0;
  }

double CV38_2StructureEngine::OBMitigationCount(int ltfBar)
  {
   int idx;
   double price = (ltfBar >= 0 && ltfBar < m_nBars) ? m_close[ltfBar] : 0;
   double atrVal = ComputeATRVal(ltfBar);
   NearestOB(ltfBar, price, atrVal, idx);
   return (idx >= 0) ? (double)m_obs[idx].mitigation_count : 0.0;
  }

double CV38_2StructureEngine::OBFreshnessEnc(int ltfBar)
  {
   int idx;
   double price = (ltfBar >= 0 && ltfBar < m_nBars) ? m_close[ltfBar] : 0;
   double atrVal = ComputeATRVal(ltfBar);
   NearestOB(ltfBar, price, atrVal, idx);
   if(idx < 0) return 0;
   string fr = m_obs[idx].freshness;
   if(StringCompare(fr, "fresh") == 0) return 1.0;
   if(StringCompare(fr, "touched") == 0) return 2.0;
   return 3.0; // stale
  }

double CV38_2StructureEngine::OBMitigationDepth(int ltfBar)
  {
   int idx;
   double price = (ltfBar >= 0 && ltfBar < m_nBars) ? m_close[ltfBar] : 0;
   double atrVal = ComputeATRVal(ltfBar);
   NearestOB(ltfBar, price, atrVal, idx);
   return (idx >= 0) ? m_obs[idx].deepest_pen : 0.0;
  }

//--- FVG queries ---
int CV38_2StructureEngine::NearestFVG(int bar, double price, double atrVal)
  {
   if(m_nFvgs == 0) return -1;
   double minDist = DBL_MAX;
   int nearestIdx = -1;
   for(int f=0; f<m_nFvgs; f++)
     {
      if(m_fvgs[f].invalidated) continue;
      if(m_fvgs[f].conf_bar > bar) continue;
      if(m_fvgs[f].inv_bar <= bar) continue;
      string lc = m_fvgs[f].lifecycle;
      if(StringCompare(lc, "open") != 0 && StringCompare(lc, "partially_filled") != 0) continue;
      double dist;
      if(price < m_fvgs[f].lower) dist = m_fvgs[f].lower - price;
      else if(price > m_fvgs[f].upper) dist = price - m_fvgs[f].upper;
      else dist = 0;
      if(dist < minDist) { minDist = dist; nearestIdx = f; }
     }
   return nearestIdx;
  }

double CV38_2StructureEngine::FVGPresent(int ltfBar)
  {
   double price = (ltfBar >= 0 && ltfBar < m_nBars) ? m_close[ltfBar] : 0;
   double atrVal = ComputeATRVal(ltfBar);
   return (NearestFVG(ltfBar, price, atrVal) >= 0) ? 1.0 : 0.0;
  }

double CV38_2StructureEngine::FVGDirectionEnc(int ltfBar)
  {
   double price = (ltfBar >= 0 && ltfBar < m_nBars) ? m_close[ltfBar] : 0;
   double atrVal = ComputeATRVal(ltfBar);
   int idx = NearestFVG(ltfBar, price, atrVal);
   if(idx < 0) return 0;
   return (m_fvgs[idx].direction == 1) ? DIR_ENC_BULL :
          ((m_fvgs[idx].direction == -1) ? DIR_ENC_BEAR : DIR_ENC_NEUT);
  }

double CV38_2StructureEngine::FVGSizeATR(int ltfBar)
  {
   double price = (ltfBar >= 0 && ltfBar < m_nBars) ? m_close[ltfBar] : 0;
   double atrVal = ComputeATRVal(ltfBar);
   int idx = NearestFVG(ltfBar, price, atrVal);
   return (idx >= 0) ? m_fvgs[idx].size_atr : 0.0;
  }

double CV38_2StructureEngine::FVGAgeBars(int ltfBar)
  {
   double price = (ltfBar >= 0 && ltfBar < m_nBars) ? m_close[ltfBar] : 0;
   double atrVal = ComputeATRVal(ltfBar);
   int idx = NearestFVG(ltfBar, price, atrVal);
   return (idx >= 0) ? (double)(ltfBar - m_fvgs[idx].conf_bar) : 0.0;
  }

double CV38_2StructureEngine::FVGFillPct(int ltfBar)
  {
   double price = (ltfBar >= 0 && ltfBar < m_nBars) ? m_close[ltfBar] : 0;
   double atrVal = ComputeATRVal(ltfBar);
   int idx = NearestFVG(ltfBar, price, atrVal);
   return (idx >= 0) ? m_fvgs[idx].fill_pct : 0.0;
  }

double CV38_2StructureEngine::FVGFreshnessEnc(int ltfBar)
  {
   double price = (ltfBar >= 0 && ltfBar < m_nBars) ? m_close[ltfBar] : 0;
   double atrVal = ComputeATRVal(ltfBar);
   int idx = NearestFVG(ltfBar, price, atrVal);
   if(idx < 0) return 0;
   string lc = m_fvgs[idx].lifecycle;
   if(StringCompare(lc, "open") == 0) return 1.0;
   if(StringCompare(lc, "partially_filled") == 0) return 2.0;
   return 3.0; // fully_filled
  }

//--- PD queries ---
double CV38_2StructureEngine::PDPosition(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars || m_nLegs == 0) return 0.5;
   // Find latest confirmed leg
   int legIdx = -1;
   for(int l=m_nLegs-1; l>=0; l--)
     {
      if(m_legs[l].conf_bar <= ltfBar) { legIdx = l; break; }
     }
   if(legIdx < 0) return 0.5;
   double hi = m_legs[legIdx].high, lo = m_legs[legIdx].low;
   double span = hi - lo;
   if(span <= 0) return 0.5;
   double pos = (m_close[ltfBar] - lo) / span;
   return MathMax(0.0, MathMin(1.0, pos));
  }

double CV38_2StructureEngine::PDLabelEnc(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars || m_nLegs == 0) return 1.0; // equilibrium/unknown
   int legIdx = -1;
   for(int l=m_nLegs-1; l>=0; l--)
     {
      if(m_legs[l].conf_bar <= ltfBar) { legIdx = l; break; }
     }
   if(legIdx < 0) return 1.0;
   double pos = PDPosition(ltfBar);
   if(pos > 0.5 + V38_2_PD_EQ_BAND) return 2.0; // premium
   if(pos < 0.5 - V38_2_PD_EQ_BAND) return 0.0; // discount
   return 1.0; // equilibrium
  }

double CV38_2StructureEngine::PDDistanceFromEq(int ltfBar)
  {
   double pos = PDPosition(ltfBar);
   return MathAbs(pos - 0.5) * 2.0;
  }

double CV38_2StructureEngine::PDLegSpanATR(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars || m_nLegs == 0) return 0;
   int legIdx = -1;
   for(int l=m_nLegs-1; l>=0; l--)
     {
      if(m_legs[l].conf_bar <= ltfBar) { legIdx = l; break; }
     }
   if(legIdx < 0) return 0;
   double span = m_legs[legIdx].high - m_legs[legIdx].low;
   double a = ComputeATRVal(ltfBar);
   return span / (a > 0 ? a : 1.0);
  }

double CV38_2StructureEngine::Alignment(double regVal, string direction)
  {
   string reg = (regVal == 2.0) ? "bullish" : ((regVal == 0.0) ? "bearish" : "neutral");
   if(direction == reg) return 1.0;
   if(direction == "neutral" || reg == "neutral") return 0.0;
   return -1.0;
  }

//+------------------------------------------------------------------+
//| Setup detection — mirrors detect_and_build_m5 candidate checks   |
//+------------------------------------------------------------------+
bool CV38_2StructureEngine::IsCandidateSetup(int bar, string direction)
  {
   if(bar < 0 || bar >= m_nBars) return false;
   double price = m_close[bar];
   double a = ComputeATRVal(bar);
   double ltf_reg = LTFRegimeEnc(bar);
   double htf_reg = HTFRegimeEnc(bar);

   // 1. Alignment: LTF regime must not contradict direction
   if(direction == "bullish" && ltf_reg == 0.0)
     {
      if(!(bar < m_nBars && m_last3ChochBull[bar])) return false;
     }
   else if(direction == "bearish" && ltf_reg == 2.0)
     {
      if(!(bar < m_nBars && m_last3ChochBear[bar])) return false;
     }

   // 2. HTF must not be against
   if(direction == "bullish" && htf_reg == 0.0) return false;
   if(direction == "bearish" && htf_reg == 2.0) return false;

   // 3. Require confluence: valid OB or open FVG in trade direction
   bool has_ob_dir = (direction == "bullish") ? m_hasObBull[bar] : m_hasObBear[bar];
   bool has_fvg_dir = (direction == "bullish") ? m_hasFvgBull[bar] : m_hasFvgBear[bar];
   if(!has_ob_dir && !has_fvg_dir) return false;

   // 4. Premium/discount gate
   double pos = PDPosition(bar);
   if(direction == "bullish" && pos > 0.6) return false;
   if(direction == "bearish" && pos < 0.4) return false;

   // 5. Require liquidity target on opposite side
   if(direction == "bullish")
     {
      if(!(bar < m_nBars && m_poolMaxPrice[bar] > price)) return false;
     }
   else
     {
      if(!(bar < m_nBars && m_poolMinPrice[bar] < price)) return false;
     }

   // 6. Quality gate
   double score = 0.4 * m_lastBcQuality[bar];
   bool hasObAny = (direction == "bullish") ? m_hasObAnyBull[bar] : m_hasObAnyBear[bar];
   if(hasObAny) score += 0.3;
   if(has_fvg_dir) score += 0.2;
   if(m_hasSweptPool[bar]) score += 0.1;
   score = MathMin(1.0, score);
   if(score < V38_2_MIN_SETUP_QUALITY) return false;

   return true;
  }

//+------------------------------------------------------------------+
//| Engine-resolved overrides (parity with Python build_feature_vector)|
//+------------------------------------------------------------------+
double CV38_2StructureEngine::PriceAt(int ltfBar)
  {
   return (ltfBar >= 0 && ltfBar < m_nBars) ? m_close[ltfBar] : 0.0;
  }

double CV38_2StructureEngine::ATRValAt(int ltfBar)
  {
   return ComputeATRVal(ltfBar);
  }

double CV38_2StructureEngine::ATRPercentileAt(int ltfBar)
  {
   if(ltfBar < 0 || ltfBar >= m_nBars) return 0.5;
   int lb = m_atrPctLookback;
   int lo = (ltfBar - lb > 0) ? ltfBar - lb : 0;
   double cur = m_atr[ltfBar];
   if(cur != cur) return 0.5; // NaN guard
   int count = 0, total = 0;
   for(int i = lo; i <= ltfBar && i < m_nBars; i++)
     {
      double v = m_atr[i];
      if(v != v) continue; // skip NaN
      total++;
      if(v <= cur) count++;
     }
   return (total > 0) ? (double)count / total : 0.5;
  }

// Mirrors Python v[52]: target = nearest OB edge (or FVG edge), then |target-price|/a.
double CV38_2StructureEngine::DistanceToEntryATR(int ltfBar, double price, double atrVal)
  {
   if(atrVal <= 0) return 0.0;
   double a = (atrVal > 0) ? atrVal : ComputeATRVal(ltfBar);
   if(a <= 0) return 0.0;
   int obIdx; NearestOB(ltfBar, price, a, obIdx);
   if(obIdx >= 0)
     {
      double target;
      if(price > m_obs[obIdx].upper) target = m_obs[obIdx].lower;
      else if(price < m_obs[obIdx].lower) target = m_obs[obIdx].upper;
      else target = price;
      return MathAbs(target - price) / a;
     }
   int fvgIdx = NearestFVG(ltfBar, price, a);
   if(fvgIdx >= 0)
     {
      double target;
      if(price > m_fvgs[fvgIdx].upper) target = m_fvgs[fvgIdx].lower;
      else if(price < m_fvgs[fvgIdx].lower) target = m_fvgs[fvgIdx].upper;
      else target = price;
      return MathAbs(target - price) / a;
     }
   return 0.0;
  }

#endif // __V38_2_STRUCTURE_MQH__
