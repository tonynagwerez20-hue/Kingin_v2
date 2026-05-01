//+------------------------------------------------------------------+
//|                                                      TestDLL.mq5 |
//|                                  Minimal ZMQ DLL Connection Test |
//+------------------------------------------------------------------+
#property copyright "Hedge System Diagnostic"
#property version   "1.00"
#property script_show_inputs

// Import ZMQ DLL
#import "libzmq.dll"
   long zmq_ctx_new();
   int zmq_ctx_destroy(long context);
#import

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
{
   Print("=== STARTING DLL TEST ===");
   
   // 1. Check if we can call a simple DLL function
   long context = zmq_ctx_new();
   
   if(context != 0)
   {
      Print("✅ SUCCESS: libzmq.dll loaded and Context created! (ID: ", context, ")");
      zmq_ctx_destroy(context);
   }
   else
   {
      Print("❌ FAILURE: libzmq.dll loaded but returned NULL context.");
   }
   
   Print("=== TEST COMPLETE ===");
}
