using Google.Protobuf;
using Pb;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using static Pb.DDMData.Types;

namespace 测试send
{
    public class UDPSend
    {


        UdpClient sendUdp = null;
        IPEndPoint iPEndPoint;

        /// <summary>
        /// 发送消息
        /// </summary>
        /// <param name="byteMsg"></param>
        /// <param name="_RemoteIPAddress"></param>
        /// <param name="_RemotePort"></param>
        private void SendMsgToClient_udp(byte[] byteMsg, int size)
        {
            try
            {
                if (sendUdp == null)
                {
                    sendUdp = new UdpClient();
                    //sendUdp.EnableBroadcast = true;
                }

                if (byteMsg == null) { return; }


                sendUdp.Send(byteMsg, size, iPEndPoint);
                //sender.Close();
            }
            catch (Exception ex)
            {
                MessageBox.Show("udp单播通信发送消息时出错：" + ex.Message);
            }
        }


        public void IniteUDP()
        {
            try
            {
                string iniPath = AppDomain.CurrentDomain.BaseDirectory + @"/Config/config.ini";
                string str_IP = Common.INIHelper.ReadSection(iniPath, "其他配置")["发送至IP"];
                string str_Port = Common.INIHelper.ReadSection(iniPath, "其他配置")["发送UDP端口"];
                int i_Port = Int32.Parse(str_Port);
                IPAddress local_ip = IPAddress.Parse(str_IP);
                iPEndPoint = new IPEndPoint(local_ip, i_Port);
                sendUdp = new UdpClient();

            }
            catch (Exception ex)
            {
                MessageBox.Show("初始化发送udp错误：" + $"{ex.Message}");
            }

        }

        /// <summary>
        /// 发送多个double变量
        /// </summary>
        /// <param name="keyVaules"></param>
        public void SendKeyVaules(Dictionary<string, double> keyVaules)
        {
            DDMData ddmData = new DDMData(); //protobuf加密
            foreach (var item in keyVaules)
            {
                string variableName = item.Key; //变量名
                double variableValue = item.Value;  //变量值

                //获取当前列的所有行数据发送出去；与配置文件内容的字段名称相对应
                ddmData.SimVars.Add(new SimVar()
                {
                    Name = variableName,
                    Type = Pb.DDMData.Types.SimVar.Types.Type.Double,
                    DoubleValue = variableValue
                });
            }

            byte[] ddmDataBytes1 = ddmData.ToByteArray();
            string byStr1 = Convert.ToBase64String(ddmDataBytes1);
            byte[] buffers1 = Encoding.ASCII.GetBytes(byStr1);

            SendMsgToClient_udp(buffers1, buffers1.Length);
        }

        /// <summary>
        /// 发送单个double变量
        /// </summary>
        /// <param name="name"></param>
        /// <param name="vaule"></param>
        public void SendKeyVaules(string name,double vaule)
        {
            DDMData ddmData = new DDMData(); //protobuf加密
            {
                string variableName = name; //变量名
                double variableValue = vaule;  //变量值

                //获取当前列的所有行数据发送出去；与配置文件内容的字段名称相对应
                ddmData.SimVars.Add(new SimVar()
                {
                    Name = variableName,
                    Type = Pb.DDMData.Types.SimVar.Types.Type.Double,
                    DoubleValue = variableValue
                });
            }

            byte[] ddmDataBytes1 = ddmData.ToByteArray();
            string byStr1 = Convert.ToBase64String(ddmDataBytes1);
            byte[] buffers1 = Encoding.ASCII.GetBytes(byStr1);

            SendMsgToClient_udp(buffers1, buffers1.Length);
        }
        public void SendKeyVaules1(string name, string name1,double vaule)
        {
            DDMData ddmData = new DDMData(); //protobuf加密
            {
                string variableName = name; //变量名
                double variableValue = vaule;  //变量值

                //获取当前列的所有行数据发送出去；与配置文件内容的字段名称相对应
                ddmData.SimVars.Add(new SimVar()
                {
                    Name = variableName,
                    Type = Pb.DDMData.Types.SimVar.Types.Type.Double,
                    DoubleValue = variableValue
                });
            }

            byte[] ddmDataBytes1 = ddmData.ToByteArray();
            string byStr1 = Convert.ToBase64String(ddmDataBytes1);
            byte[] buffers1 = Encoding.ASCII.GetBytes(byStr1);

            SendMsgToClient_udp(buffers1, buffers1.Length);
        }

        /// <summary>
        ///发送数据udp 
        /// </summary>
        /// <param name="keyVaules"></param>
        public void SendVaules(Dictionary<string, double> keyVaules)
        {
            byte[] bytes = new byte[keyVaules.Count * 8];
            List<byte> buffers = new List<byte>();
            foreach (var kvp in keyVaules)
            {
                buffers.AddRange(BitConverter.GetBytes(kvp.Value));
            }
            bytes = buffers.ToArray();
            SendMsgToClient_udp(bytes, bytes.Length);
        }
    }
}
