//+------------------------------------------------------------------+
//|                                          V38_Calibrator.mqh       |
//|  Isotonic / sigmoid calibrator mirror of backend calibration.py  |
//|  Loads v38_calibrator.json (x_thresholds/y_thresholds or coef/   |
//|  intercept) and applies the same post-ONNX mapping the Python     |
//|  inference wrapper uses. This MUST be applied to the raw ONNX      |
//|  output probability to match training-time calibration.           |
//+------------------------------------------------------------------+
#property strict
#ifndef __V38_CALIBRATOR_MQH__
#define __V38_CALIBRATOR_MQH__

class CV38Calibrator
  {
private:
   double            m_xThr[];      // isotonic x_thresholds
   double            m_yThr[];      // isotonic y_thresholds
   double            m_coef[2];     // sigmoid coef
   double            m_intercept[2];
   string            m_method;     // "isotonic" | "sigmoid" | "none"
   bool              m_loaded;

public:
   CV38Calibrator() { m_loaded=false; m_method="none"; }

   bool Load(const string filename)
     {
      m_loaded=false; m_method="none";
      ArrayResize(m_xThr,0); ArrayResize(m_yThr,0);
      int h=FileOpen(filename, FILE_READ|FILE_TXT|FILE_ANSI);
      if(h==INVALID_HANDLE)
        {
         Print("V38 Calibrator: FileOpen FAILED for '", filename, "' err=", GetLastError());
         return false;
        }
      string txt="";
      while(!FileIsEnding(h)) txt+=FileReadString(h)+" ";
      FileClose(h);
      return ParseFromText(txt);
     }

   // Load calibrator from an in-memory JSON string (e.g. a #resource buffer
   // converted via CharArrayToString). Used for the Strategy Tester sandbox,
   // where MQL5\Files is not reachable from the tester agent working directory.
   bool LoadFromString(const string json)
     {
      m_loaded=false; m_method="none";
      ArrayResize(m_xThr,0); ArrayResize(m_yThr,0);
      return ParseFromText(json);
     }

   // Parse the calibrator JSON text already loaded into memory. Shared by
   // Load() (from file) and LoadFromString() (from embedded #resource).
   bool ParseFromText(const string txt)
     {
      if(StringLen(txt)==0) { return false; }
      // method detection (isotonic chosen by canonical frozen calibrator)
      m_method = (StringFind(txt,"\"isotonic\"")>=0 ||
                  StringFind(txt,"\"X_thresholds\"")>=0 ||
                  StringFind(txt,"\"x_thresholds\"")>=0) ? "isotonic" :
                 ((StringFind(txt,"\"sigmoid\"")>=0 ||
                   StringFind(txt,"\"coef\"")>=0) ? "sigmoid" : "none");
      if(m_method=="isotonic")
        {
         // Canonical frozen JSON uses capital "X_thresholds" and "y_thresholds".
         // Accept both capitalizations (case-insensitive key search) so the
         // calibrator never silently fails on a key-spelling mismatch.
         if(!ParseArray(txt, "X_thresholds", m_xThr))
            ParseArray(txt, "x_thresholds", m_xThr);
         if(!ParseArray(txt, "y_thresholds", m_yThr))
            ParseArray(txt, "Y_thresholds", m_yThr);
         if(ArraySize(m_xThr)==0 || ArraySize(m_yThr)==0)
           {
            Print("V38 Calibrator: isotonic arrays EMPTY after parse (key mismatch?). "
                  "xThr=", ArraySize(m_xThr), " yThr=", ArraySize(m_yThr));
            m_method="none";
            return false;
           }
        }
      else if(m_method=="sigmoid")
        {
         if(!ParseArray(txt, "coef", m_coef))
            Print("V38 Calibrator: sigmoid coef array missing");
         if(!ParseArray(txt, "intercept", m_intercept))
            Print("V38 Calibrator: sigmoid intercept array missing");
        }
      m_loaded=true;
      Print("V38 Calibrator: loaded method=", m_method,
            " points=", ArraySize(m_xThr));
      return true;
     }

   bool   IsLoaded()  { return m_loaded; }
   string Method()    { return m_method; }

   // Apply calibrator to raw probability p in [0,1]
   double Apply(double p)
     {
      if(!m_loaded || m_method=="none") return p;
      if(m_method=="isotonic") return IsotonicMap(p);
      if(m_method=="sigmoid") return SigmoidMap(p);
      return p;
     }

private:
   double IsotonicMap(double p)
     {
      int n=ArraySize(m_xThr);
      if(n==0) return p;
      if(p<=m_xThr[0]) return m_yThr[0];
      if(p>=m_xThr[n-1]) return m_yThr[n-1];
      // binary search for the interval
      int lo=0, hi=n-1;
      while(hi-lo>1)
        {
         int mid=(lo+hi)/2;
         if(m_xThr[mid]<=p) lo=mid; else hi=mid;
        }
      double x0=m_xThr[lo], x1=m_xThr[hi];
      double y0=m_yThr[lo], y1=m_yThr[hi];
      if(x1<=x0) return y0;
      double t=(p-x0)/(x1-x0);
      return y0+t*(y1-y0);
     }

   double SigmoidMap(double p)
     {
      double eps=1e-6;
      double pc=MathMax(eps, MathMin(1.0-eps, p));
      double logit=MathLog(pc/(1.0-pc));
      // logistic(coef[0]*logit + intercept[0])
      double z=m_coef[0]*logit + m_intercept[0];
      return 1.0/(1.0+MathExp(-z));
     }

   // case-insensitive JSON numeric-array extractor. Returns true on success.
   // Matches the quoted key `"key"` (case-insensitive), then the following
   // `[ ... ]`. Robust to the canonical capitalization (X_thresholds) and
   // the export.py lower-case variant (x_thresholds).
   bool ParseArray(const string txt, const string key, double &arr[])
     {
      int kpos=FindKeyCI(txt, key);
      if(kpos<0) { ArrayResize(arr,0); return false; }
      int colon=StringFind(txt, ":", kpos);
      if(colon<0) { ArrayResize(arr,0); return false; }
      int lb=StringFind(txt, "[", colon);
      if(lb<0) { ArrayResize(arr,0); return false; }
      int rb=StringFind(txt, "]", lb);
      if(rb<0) { ArrayResize(arr,0); return false; }
      string body=StringSubstr(txt, lb+1, rb-lb-1);
      string parts[];
      int n=StringSplit(body, ',', parts);
      if(n<=0) { ArrayResize(arr,0); return false; }
      ArrayResize(arr, n);
      for(int i=0;i<n;i++)
        {
         string s=parts[i];
         StringTrimLeft(s); StringTrimRight(s);
         // strip trailing/leading quotes if a string slipped in
         if(StringLen(s)>0 && StringGetCharacter(s,0)=='\"')
            s=StringSubstr(s,1);
         int L=StringLen(s);
         if(L>0 && StringGetCharacter(s,L-1)=='\"')
            s=StringSubstr(s,0,L-1);
         arr[i]=StringToDouble(s);
        }
      return (ArraySize(arr)>0);
     }

   // Find the position of the quoted key `"<key>"` case-insensitively.
   int FindKeyCI(const string txt, const string key)
     {
      string lowerTxt=txt;
      StringToLower(lowerTxt);
      string quoted="\""+key+"\"";
      string lowerQ=quoted;
      StringToLower(lowerQ);
      return StringFind(lowerTxt, lowerQ);
     }
  };

#endif // __V38_CALIBRATOR_MQH__
