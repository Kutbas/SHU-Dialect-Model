// fayApp.js
class FayInterface {
  constructor(baseWsUrl, baseApiUrl, vueInstance) {
    this.baseWsUrl = baseWsUrl;
    this.baseApiUrl = baseApiUrl;
    this.websocket = null;
    this.vueInstance = vueInstance; 
  }

  connectWebSocket() {
    if (this.websocket) {
      this.websocket.onopen = null;
      this.websocket.onmessage = null;
      this.websocket.onclose = null;
      this.websocket.onerror = null;
    }

    this.websocket = new WebSocket(this.baseWsUrl);

    this.websocket.onopen = () => {
      console.log('WebSocket connection opened');
    };

    this.websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleIncomingMessage(data);
    };

    this.websocket.onclose = () => {
      console.log('WebSocket connection closed. Attempting to reconnect...');
      setTimeout(() => this.connectWebSocket(), 5000); 
    };

    this.websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  async fetchData(url, options = {}) {
    try {
      const response = await fetch(url, options);
      if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Error fetching data:', error);
      return null;
    }
  }

  getVoiceList() {
    return this.fetchData(`${this.baseApiUrl}/api/get-voice-list`);
  }

  getAudioDeviceList() {
    return this.fetchData(`${this.baseApiUrl}/api/get-audio-device-list`);
  }

  submitConfig(config) {
    return this.fetchData(`${this.baseApiUrl}/api/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config })
    });
  }

  controlEyes(state) {
    return this.fetchData(`${this.baseApiUrl}/api/control-eyes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state })
    });
  }

  startLive() {
    return this.fetchData(`${this.baseApiUrl}/api/start-live`, {
      method: 'POST'
    });
  }

  stopLive() {
    return this.fetchData(`${this.baseApiUrl}/api/stop-live`, {
      method: 'POST'
    });
  }

  getRunStatus() {
    return this.fetchData(`${this.baseApiUrl}/api/get_run_status`, {
      method: 'POST'
    });
  }

  getMessageHistory(username) {
    return new Promise((resolve, reject) => {
      const url = `${this.baseApiUrl}/api/get-msg`;
      const xhr = new XMLHttpRequest();
      xhr.open("POST", url);
      xhr.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
      const send_data = `data=${encodeURIComponent(JSON.stringify({ username }))}`;
      xhr.send(send_data);

      xhr.onreadystatechange = function () {
        if (xhr.readyState === 4) {
          if (xhr.status === 200) {
            try {
              const data = JSON.parse(xhr.responseText);
              if (data && data.list) {
                const combinedList = data.list.flat(); 
                resolve(combinedList);
              } else {
                resolve([]);
              }
            } catch (e) {
              console.error('Error parsing response:', e);
              reject(e);
            }
          } else {
            reject(new Error(`Request failed with status ${xhr.status}`));
          }
        }
      };
    });
  }

  getUserList() {
    return this.fetchData(`${this.baseApiUrl}/api/get-member-list`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
  }

  getData() {
    return this.fetchData(`${this.baseApiUrl}/api/get-data`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
}

  getTime(){
    const date = new Date();
    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const seconds = date.getSeconds().toString().padStart(2, '0');
    const currentDateTime = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    return currentDateTime;
  }

  handleIncomingMessage(data) {
    const vueInstance = this.vueInstance; 
  //   console.log('Incoming message:', data);
    if (data.liveState !== undefined) {
      vueInstance.liveState = data.liveState;
      if (data.liveState === 1) {
        vueInstance.configEditable = false;
      } else if (data.liveState === 0) {
        vueInstance.configEditable = true;
      }
    }

    if (data.voiceList !== undefined) {
      vueInstance.voiceList = data.voiceList.map(voice => ({
        value: voice.id,
        label: voice.name
      }));
    }

    if (data.deviceList !== undefined) {
      vueInstance.deviceList = data.deviceList.map(device => ({
        value: device,
        label: device
      }));
    }

    if (data.panelMsg !== undefined) {
      vueInstance.panelMsg = data.panelMsg; 
    }
    if (data.robot) {
      console.log(data.robot)
      vueInstance.$set(vueInstance, 'robot', data.robot); 
      }
    if (data.panelReply !== undefined) {
      vueInstance.panelReply = data.panelReply.content; 
      const userExists = vueInstance.userList.some(user => user[1] === data.panelReply.username);
      if (!userExists) {
        vueInstance.userList.push([data.panelReply.uid, data.panelReply.username]);
      }
      if (vueInstance.selectedUser && data.panelReply.username === vueInstance.selectedUser[1]) {
        if ('is_adopted' in data.panelReply && data.panelReply.is_adopted === true) {
          vueInstance.messages.push({
              id: data.panelReply.id,
              username: data.panelReply.username,
              content: data.panelReply.content,
              type: data.panelReply.type,
              timetext: this.getTime(),
              is_adopted: 1
          });
      } else {
        vueInstance.messages.push({
          id: data.panelReply.id,
          username: data.panelReply.username,
          content: data.panelReply.content,
          type: data.panelReply.type,
          timetext: this.getTime(),
          is_adopted: 0
      });
      }

        vueInstance.$nextTick(() => {
          const chatContainer = vueInstance.$el.querySelector('.chatmessage');
          if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
          }
        });
      }
    }

    if (data.is_connect !== undefined) {
      vueInstance.isConnected = data.is_connect;
    }

    if (data.remote_audio_connect !== undefined) {
      vueInstance.remoteAudioConnected = data.remote_audio_connect;
    }
  }

  clearUserHistory(username) {
    return this.fetchData(`${this.baseApiUrl}/api/clear-history`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username })
    });
  }
}

new Vue({
  el: '#app',
  delimiters: ["[[", "]]"],
  data() {
    return {
      messages: [],
      newMessage: '',
      fayService: null,
      liveState: 0,
      isConnected: false,
      remoteAudioConnected: false,
      userList: [],
      selectedUser: null,
      loading: false,
      chatMessages: {},
      panelMsg: '', 
      panelReply: '', 
      base_url: 'http://127.0.0.1:5000',
      play_sound_enabled: false,
      source_record_enabled: false,
      userListTimer: null,
      isSidebarVisible: true,
      now_asr_mode: '',
      isContentVisible: true,
      currentPage: 'index',
      backgroundImages: ['Bg_pic.png', 'Bg_pic2.png', 'Bg_pic3.png','Bg_pic4.png'],
      currentBgIndex: 0,
      currentVoiceMode: 0
    };
  },
  created() {
    this.initFayService(); 
    this.getData();
    this.getAsrMode();
    this.startUserListTimer();
    const savedState = localStorage.getItem('sidebarState');
    if (savedState !== null) {
      this.isSidebarVisible = savedState === 'true';
    }
    const savedBgIndex = localStorage.getItem('backgroundIndex');
    if (savedBgIndex !== null) {
      this.currentBgIndex = parseInt(savedBgIndex);
    }
    const savedVoiceMode = localStorage.getItem('voiceMode');
    if (savedVoiceMode !== null) {
      this.currentVoiceMode = parseInt(savedVoiceMode);
    }
    this.applyBackground();
  },
  mounted() {
    window.addEventListener('resize', this.handleResize);
    this.handleResize();
  },
  methods: {
    initFayService() {
      this.fayService = new FayInterface('ws://127.0.0.1:10003', this.base_url, this);
      this.fayService.connectWebSocket();
      this.fayService.websocket.addEventListener('open', () => {
        this.loadUserList();
    });
    },
    sendMessage() {
      let _this = this;
      let text = _this.newMessage;
      if (!text) {
        alert('请输入内容');
        return;
      }
      if (_this.selectedUser === 'others' && !_this.othersUser) {
        alert('请输入自定义用户名');
        return;
      }
      if (this.liveState != 1) {
        alert('请先开启服务');
        return;
      }
      let usernameToSend = _this.selectedUser === 'others' ? _this.othersUser : _this.selectedUser[1];

      this.timer = setTimeout(() => {
        let height = document.querySelector('.chatmessage').scrollHeight;
        document.querySelector('.chatmessage').scrollTop = height;
      }, 1000);
      _this.newMessage = '';
      let url = `${this.base_url}/api/send`;
      let send_data = {
        "msg": text,
        "username": usernameToSend
      };

      let xhr = new XMLHttpRequest();
      xhr.open("post", url);
      xhr.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
      xhr.send('data=' + encodeURIComponent(JSON.stringify(send_data)));
      let executed = false;
      xhr.onreadystatechange = async function () {
        if (!executed && xhr.status === 200) {
          executed = true;
        }
      };
    },
    getAsrMode() {
      fetch('/api/get-asr-mode', {
        method: 'POST'
      })
      .then(response => {
        if (!response.ok) {
          throw new Error('请求出错');
        }
        return response.json();
      })
      .then(data => {
        console.log("当前ASR模型：", data.asr_mode);
        this.now_asr_mode = data.asr_mode;
      })
      .catch(error => {
        console.error('获取ASR模型出错：', error);
      });
    },
    
    getData() {
      this.fayService.getRunStatus().then((data) => {
          if (data) {
              if(data.status){
                  this.liveState = 1;
                  this.configEditable = false;
              }else{
                  this.liveState = 0;
                  this.configEditable = true;
              }
              
          }
      });
      this.fayService.getData().then((data) => {
          if (data) {
              this.updateConfigFromData(data.config);
          }
      });
  },
  updateConfigFromData(config) {
    
      if (config.interact) {
          this.play_sound_enabled = config.interact.playSound;
      }
      if (config.source && config.source.record) {
          this.source_record_enabled = config.source.record.enabled;
      }
  },
  saveConfig() {
    let url = `${this.base_url}/api/submit`;
    let send_data = {
        "config": {
            "source": {
                "record": {
                    "enabled": this.source_record_enabled,
                },
            },
            "interact": {
                "playSound": this.play_sound_enabled,
            }
        }
    };

    let xhr = new XMLHttpRequest()
    xhr.open("post", url)
    xhr.setRequestHeader("Content-type", "application/x-www-form-urlencoded")
    xhr.send('data=' + JSON.stringify(send_data))
    let executed = false
    xhr.onreadystatechange = async function () {
        if (!executed && xhr.status === 200) {
            try {
                let data = await eval('(' + xhr.responseText + ')')
                executed = true
            } catch (e) {
            }
        }
    }
},
  changeRecord(){
    if(this.source_record_enabled){
      this.source_record_enabled = false
    }else{
      this.source_record_enabled = true
    }
    this.saveConfig()
  },
  changeSound(){
    if(this.play_sound_enabled){
      this.play_sound_enabled = false
    }else{
      this.play_sound_enabled = true
    }
    this.saveConfig()
  },
    loadUserList() {
      this.fayService.getUserList().then((response) => {
        if (response && response.list) {
          if (response.list.length == 0){
            info = [];
            info[0] = 1;
            info[1] = 'User';
            this.userList.push(info)
            this.selectUser(info);
          }else{
          this.userList = response.list;
          if (!this.selectedUser) {
            this.selectUser(this.userList[0]);
          }
        }
      }
      });
    },
    startUserListTimer() {
      if (this.userListTimer) {
        clearInterval(this.userListTimer);
      }
      this.userListTimer = setInterval(() => {
        this.loadUserList();
      }, 30000);
    },
    beforeDestroy() {
      if (this.userListTimer) {
        clearInterval(this.userListTimer);
        this.userListTimer = null;
      }
      window.removeEventListener('resize', this.handleResize);
    },
    selectUser(user) {
      this.selectedUser = user;
      this.fayService.websocket.send(JSON.stringify({ "Username": user[1] }));
      this.loadMessageHistory(user[1], 'common'); 
    },
    startLive() {
      this.liveState = 2
      this.fayService.startLive().then(() => {
        this.sendSuccessMsg('已开启！');
        this.getData();
      });
  },
  stopLive() {
      this.fayService.stopLive().then(() => {
          this.liveState = 3
          this.sendSuccessMsg('已关闭！');
      });
  },

    loadMessageHistory(username, type) {
      this.fayService.getMessageHistory(username).then((response) => {
        if (response) {
          this.messages = response;
          if(type == 'common'){
          this.$nextTick(() => {
            const chatContainer = this.$el.querySelector('.chatmessage');
            if (chatContainer) {
              chatContainer.scrollTop = chatContainer.scrollHeight;
            }
          });
        }
        }
      });
    },
    sendSuccessMsg(message) {
      this.$notify({
          title: '成功',
          message,
          type: 'success',
      });
  
},
    toggleSidebar() {
      this.isSidebarVisible = !this.isSidebarVisible;
      localStorage.setItem('sidebarState', this.isSidebarVisible);
    },

    toggleContentVisibility() {
      this.isContentVisible = !this.isContentVisible;
    },

    changeASRModel() {
      const newModel = this.now_asr_mode === 'huyu' ? 'xunfei' : 'huyu';
      fetch('/api/change-asr-mode', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ asrModel: newModel })
      })
      .then(response => response.json())
      .then(data => {
        if (data.result === 'successful') {
          this.now_asr_mode = newModel;
          this.$notify({
            title: '成功',
            message: `ASR模型已切换为${newModel}`,
            type: 'success'
          });
        } else {
          this.$notify({
            title: '错误',
            message: data.message || '切换ASR模型失败',
            type: 'error'
          });
        }
      })
      .catch(error => {
        this.$notify({
          title: '错误',
          message: error.message || '请求失败',
          type: 'error'
        });
      });
    },
    switchPage(page) {
      this.currentPage = page;
      if (page === 'setting') {
        window.location.href = '/setting';
      } else {
        window.location.href = '/';
      }
    },
    computed: {
      isIndexPage() {
        return this.currentPage === 'index' || window.location.pathname === '/';
      },
      isSettingPage() {
        return this.currentPage === 'setting' || window.location.pathname === '/setting';
      }
    },
    changeBackground() {
      this.currentBgIndex = (this.currentBgIndex + 1) % this.backgroundImages.length;
      localStorage.setItem('backgroundIndex', this.currentBgIndex);
      this.applyBackground();
      this.$notify({
        title: '成功',
        message: '背景已切换',
        type: 'success'
      });
    },
    applyBackground() {
      document.body.style.backgroundImage = `url(static/images/${this.backgroundImages[this.currentBgIndex]})`;
    },
    clearHistory() {
      if (!this.selectedUser) {
        this.$notify({
          title: '错误',
          message: '请先选择一个用户',
          type: 'error'
        });
        return;
      }
      
      this.fayService.clearUserHistory(this.selectedUser[1]).then(response => {
        if (response && response.result === 'successful') {
          this.messages = [];
          this.$notify({
            title: '成功',
            message: '聊天记录已清除',
            type: 'success'
          });
        } else {
          this.$notify({
            title: '错误',
            message: response?.message || '清除聊天记录失败',
            type: 'error'
          });
        }
      });
    },
    changeVoiceMode() {
      this.currentVoiceMode = (this.currentVoiceMode + 1) % 3;
      
      localStorage.setItem('voiceMode', this.currentVoiceMode);
      
      fetch('/api/change-voice-mode', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ voiceMode: this.currentVoiceMode })
      })
      .then(response => response.json())
      .then(data => {
        if (data.result === 'successful') {
          let modeName = '';
          switch(this.currentVoiceMode) {
            case 0: modeName = '女声模式'; break;
            case 1: modeName = '男声模式'; break;
            case 2: modeName = '朗诵模式'; break;
          }
          
          this.$notify({
            title: '成功',
            message: `已切换为${modeName}`,
            type: 'success'
          });
        } else {
          this.$notify({
            title: '错误',
            message: data.message || '切换语音模式失败',
            type: 'error'
          });
        }
      })
      .catch(error => {
        this.$notify({
          title: '错误',
          message: '请求失败: ' + error.message,
          type: 'error'
        });
      });
    }
  }
});
