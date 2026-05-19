using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Pb;

namespace DotNetWinApp
{
    public class UDPClient
    {
        Thread thread;
        Socket _udpReceiveSocket;

        #region ͨ��ί��
        //����ί��
        public delegate void SendDataEventHandler(double time, Dictionary<string, double> data);
        //�����¼�
        public event SendDataEventHandler SendData;
        #endregion

        /// <summary>
        /// ��ʼ��udp����- ������Ϣ
        /// </summary>
        public void UdpClientInite(string ip = "127.0.0.1", int port = 12345)
        {
            try
            {
                IPAddress local_ip = IPAddress.Parse(ip);
                
                if (_udpReceiveSocket == null)
                {
                    _udpReceiveSocket = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp);
                    IPEndPoint IpClient = new IPEndPoint(local_ip, port);
                    _udpReceiveSocket.Bind(IpClient);
                }

                if (thread == null)
                {
                    thread = new Thread(new ThreadStart(clientListen));
                    thread.IsBackground = true;
                    thread.Start();
                }
                Console.WriteLine($"[UDP] Listening on {ip}:{port}");
            }
            catch (Exception ex)
            {
                Console.WriteLine("��ʼ��udp���ն���ʱ������" + ex.Message);
            }
        }

        private void clientListen()
        {
            IPEndPoint sender = new IPEndPoint(IPAddress.Any, 0);
            EndPoint _udpRemotePoint1 = (EndPoint)(sender);
            int recv;

            byte[] buffers = new byte[102400];
            while (true)
            {
                try
                {
                    if (_udpReceiveSocket == null) { Thread.Sleep(100); continue; }

                    buffers = new byte[102400];
                    recv = _udpReceiveSocket.ReceiveFrom(buffers, ref _udpRemotePoint1);
                    if (recv > 0)
                    {
                        // ���˲�ת��Ϊ�ֽ�����
                        byte[] receivedBytes = new byte[recv];
                        Array.Copy(buffers, receivedBytes, recv);

                        // �ⲿ���߷������� Base64 ������ַ������ֽ���ʽ��
                        string base64String = Encoding.ASCII.GetString(receivedBytes);
                        byte[] protoBytes = Convert.FromBase64String(base64String);
                        
                        DDMData ddmData = Pb.DDMData.Parser.ParseFrom(protoBytes);

                        Dictionary<string, double> receive_data = new Dictionary<string, double>();
                        double time = ddmData.SimTime;

                        foreach (var item in ddmData.SimVars)
                        {
                            receive_data[item.Name] = item.DoubleValue;
                        }
                        SendData?.Invoke(time, receive_data);
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine("�������ݽ���������" + ex.Message);
                    Thread.Sleep(10);
                }
            }
        }
    }
}
