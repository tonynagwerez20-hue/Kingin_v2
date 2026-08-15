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
      int h=FileOpen(filename, FILE_READ|FILE_TXT|FILE_ANSI);
      if(h==INVALID_HANDLE) { m_method="none"; m_loaded=false; return false; }
      string txt="";
      while(!FileIsEnding(h)) txt+=FileReadString(h)+" ";
      FileClose(h);
      // minimal JSON parse (keys we care about)
      m_method = (StringFind(txt,"\"isotonic\"")>=0) ? "isotonic" :
                 ((StringFind(txt,"\"sigmoid\"")>=0) ? "sigmoid" : "none");
      if(m_method=="isotonic")
        {
         ParseArray(txt, "\"x_thresholds\"", m_xThr);
         ParseArray(txt, "\"y_thresholds\"", m_yThr);
        }
      else if(m_method=="sigmoid")
        {
         ParseArray(txt, "\"coef\"", m_coef);
         ParseArray(txt, "\"intercept\"", m_intercept);
        }
      m_loaded=true;
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

   // crude JSON array extractor for numeric arrays
   void ParseArray(const string txt, const string key, double &arr[])
     {
      int kpos=StringFind(txt, key);
      if(kpos<0) { ArrayResize(arr,0); return; }
      int colon=StringFind(txt, ":", kpos);
      int lb=StringFind(txt, "[", colon);
      int rb=StringFind(txt, "]", lb);
      if(colon<0||lb<0||rb<0) { ArrayResize(arr,0); return; }
      string body=StringSubstr(txt, lb+1, rb-lb-1);
      string parts[];
      int n=StringSplit(body, ',', parts);
      ArrayResize(arr, n);
      for(int i=0;i<n;i++)
        {
         string s=parts[i];
         StringTrimLeft(s); StringTrimRight(s);
         arr[i]=StringToDouble(s);
        }
     }
  };

#endif // __V38_CALIBRATOR_MQH__
