const { createApp, nextTick } = Vue;

createApp({
  data() {
    return {
      apiBaseUrl: localStorage.getItem('apiBaseUrl') || 'http://10.10.7.66:5000/api',
      token: localStorage.getItem('apiKey') || '',
      authError: '',
      barcode: '',
      material: null,
      recordType: 'in',
      quantity: 1,
      loading: false,
      message: '',
      messageType: 'success',
      records: [],
      currentPage: 'scan',
      barcodeLoading: false,
      barcodeError: '',
      materials: [],
      allBarcodesGenerated: [],
      resizeObserver: null,
    };
  },
  async mounted() {
    const storedToken = localStorage.getItem('apiKey');
    
    if (!storedToken) {
        this.authError = '尚未取得授權，請確保已從主頁面登入。';
        this.token = '';
        localStorage.removeItem('apiKey');
    } else {
        this.token = storedToken;
        this.authError = '';
        try {
            await this.loadMaterials();  
        } catch (e) {
            console.error('Error during initial material load:', e);
        }
    }
    
    this.loadRecords();
    this.setupResizeObserver();
  },
  beforeUnmount() {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
  },
  watch: {
      currentPage() {
          this.sendHeightToParent();
      }
  },
  methods: {
    sendHeightToParent() {
      nextTick(() => {
        const newHeight = document.documentElement.scrollHeight;
        parent.postMessage({ type: 'adjustHeight', height: newHeight }, '*');
      });
    },
    
    setupResizeObserver() {
        if ('ResizeObserver' in window) {
            this.resizeObserver = new ResizeObserver(() => {
                this.sendHeightToParent();
            });
            this.resizeObserver.observe(this.$el);
        }
        this.sendHeightToParent();
    },

    async loadMaterials() {
      try {
        const res = await axios.get(`${this.apiBaseUrl.replace(/\/$/, '')}/materials`, {
          headers: { Authorization: `Bearer ${this.token}` }
        });
        this.materials = res.data || [];
        this.authError = '';
        return this.materials;
      } catch (e) {
        console.error('取得物料列表失敗', e);
        this.materials = [];
        if (e.response && e.response.status === 401) {
            this.authError = '授權失效，請重新登入系統獲取新的Token。';
            this.token = '';
            localStorage.removeItem('apiKey');
        } else {
            this.authError = '無法連接後端服務或載入資料，請檢查API網址或網路連線。';
        }
        throw e;
      }
    },

    async fetchMaterialByBarcode() {
      this.message = '';
      this.material = null;
      if (!this.barcode.trim()) {
        this.message = '請輸入或掃描條碼';
        this.messageType = 'error';
        return;
      }
      this.loading = true;
      try {
        const res = await axios.get(`${this.apiBaseUrl.replace(/\/$/, '')}/materials/barcode/${encodeURIComponent(this.barcode.trim())}`, {
          headers: { Authorization: `Bearer ${this.token}` }
        });
        if (res.data) {
          this.material = res.data;
          this.message = '';
          this.quantity = 1;
        } else {
          this.message = '找不到對應的物料資料';
          this.messageType = 'error';
        }
      } catch (error) {
        this.message = '查詢物料失敗，請稍後再試';
        this.messageType = 'error';
      } finally {
        this.loading = false;
        this.sendHeightToParent();
      }
    },

    async submitRecord() {
      this.message = '';
      if (!this.material) {
        this.message = '請先掃描並選擇物料';
        this.messageType = 'error';
        return;
      }
      if (!this.quantity || this.quantity < 1) {
        this.message = '數量必須大於等於1';
        this.messageType = 'error';
        return;
      }
      this.loading = true;
      try {
        const payload = {
          item_id: this.material.item_id,
          type: this.recordType,
          quantity: this.quantity
        };
        const res = await axios.post(`${this.apiBaseUrl.replace(/\/$/, '')}/inventory/record`, payload, {
          headers: { Authorization: `Bearer ${this.token}` }
        });
        if (res.data && res.data.success) {
          this.message = `成功記錄${this.recordType === 'in' ? '入庫' : '出庫'} ${this.quantity} ${this.material.unit}。`;
          this.messageType = 'success';
          await this.fetchMaterialByBarcode();

          const recordQuantity = (res.data.record && typeof res.data.record.quantity === 'number') ? res.data.record.quantity : this.quantity;

          this.addRecordToList({
            id: Date.now(),
            timestamp: new Date().toISOString(),
            item_id: res.data.material.item_id,
            name: res.data.material.name,
            type: this.recordType,
            quantity: recordQuantity,
            operator: '使用者'
          });
          this.barcode = '';
          this.quantity = 1;
          if (window.parent !== window) {
            window.parent.postMessage({ type: 'inventoryUpdated' }, '*');  
          }
        } else {
          this.message = res.data.message || '操作失敗，請稍後再試';
          this.messageType = 'error';
        }
      } catch (error) {
        console.error('submitRecord error:', error.response || error);
        if (error.response && error.response.data && error.response.data.error) {
          this.message = error.response.data.error;
        } else {
          this.message = '送出失敗，請稍後再試';
        }
        this.messageType = 'error';
      } finally {
        this.loading = false;
        this.sendHeightToParent();
      }
    },

    addRecordToList(record) {
      this.records.unshift(record);
      if (this.records.length > 50) {
        this.records.splice(50);
      }
      this.saveRecords();
    },

    saveRecords() {
      localStorage.setItem('inBarcodeRecords', JSON.stringify(this.records));
    },

    loadRecords() {
      const saved = localStorage.getItem('inBarcodeRecords');
      if (saved) {
        try {
          this.records = JSON.parse(saved);
        } catch {
          this.records = [];
        }
      }
    },

    clearRecords() {
      if (confirm('確定要清除所有出入庫紀錄嗎？')) {
        this.records = [];
        this.saveRecords();
        if (window.parent !== window) {
          window.parent.postMessage({ type: 'inventoryUpdated' }, '*');
        }
      }
    },

    formatDateTime(dateStr) {
      const d = new Date(dateStr);
      if (isNaN(d)) return dateStr;
      return d.toLocaleString();
    },

    async generateAllBarcodes() {
      try {
        this.barcodeError = '';
        this.allBarcodesGenerated = [];
        let barcodeMissingCount = 0;
        let svgElementNotFoundCount = 0;

        if (this.materials.length === 0) {
          this.barcodeError = '無物料資料可製作條碼';
          return;
        }
        this.barcodeLoading = true;
        await nextTick();

        this.allBarcodesGenerated = [...this.materials];
        await nextTick();

        // 清空所有SVG內容，避免重複繪製
        this.allBarcodesGenerated.forEach(item => {
          const svgId = 'barcodeSvgAll-' + item.item_id;
          const svgElement = document.getElementById(svgId);
          if (svgElement) svgElement.innerHTML = '';
        });

        for (const item of this.allBarcodesGenerated) {
          const svgId = 'barcodeSvgAll-' + item.item_id;
          const svgElement = document.getElementById(svgId);

          if (!svgElement) {
            console.error(`SVG element ${svgId} not found for item ${item.item_id}. Skipping barcode generation.`);
            svgElementNotFoundCount++;
            continue;
          }

          if (!item.barcode) {
            console.warn(`物料編號 ${item.item_id} 缺少條碼資料，跳過製作條碼圖形。`);
            barcodeMissingCount++;
            continue;
          }

          try {
            // 先清空
            svgElement.innerHTML = '';

            JsBarcode(`#${svgId}`, item.barcode, {
              format: "code128",
              lineColor: "#4a6fdc",
              width: 2,
              height: 80,
              displayValue: true,
              fontSize: 16,
              font: "monospace",  // 強制字型
              margin: 10
            });

            await nextTick();
            await new Promise(resolve => setTimeout(resolve, 50)); // 等待渲染

          } catch (innerError) {
            console.error(`Error processing barcode for item ${item.item_id}:`, innerError);
          }
        }

        if (barcodeMissingCount > 0 || svgElementNotFoundCount > 0) {
          this.barcodeError = `有 ${barcodeMissingCount} 個物料缺少條碼資料，${svgElementNotFoundCount} 個條碼圖形元素未找到。`;
        } else {
          this.barcodeError = '';
        }
      } catch (e) {
        console.error('generateAllBarcodes error:', e);
        this.barcodeError = '一鍵全部製作過程中發生未知錯誤，請稍後再試。';
      } finally {
        this.barcodeLoading = false;
        this.sendHeightToParent();
      }
    },

    async exportBarcodesWithTextToPdf() {
      if (this.allBarcodesGenerated.length === 0) {
        alert('沒有可匯出的條碼。請先製作條碼。');
        return;
      }

      const doc = new window.jspdf.jsPDF({
        unit: 'pt',
        format: 'a4'
      });
      
      // 設定中文字型
      doc.setFont('wqy-zenhei'); // 設定字型為 'wqy-zenhei' (文泉驛微米黑)

      const margin = 40;
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();

      let yOffset = margin;
      const lineHeight = 18;
      const barcodeImgHeight = 100; // 調整高度以包含文字
      const barcodeImgWidth = 320;
      const spacing = 20;

      for (const item of this.allBarcodesGenerated) {
        const neededHeight = lineHeight * 3 + barcodeImgHeight + spacing;
        if (yOffset + neededHeight > pageHeight - margin) {
          doc.addPage();
          yOffset = margin;
          doc.setFont('wqy-zenhei'); // 換頁後也要重新設定字型
        }

        // 文字部分
        doc.setFontSize(12);
        doc.setTextColor(20, 20, 20);
        doc.text(`物料名稱: ${item.name}`, margin, yOffset);
        yOffset += lineHeight;
        doc.text(`物料編號: ${item.item_id}`, margin, yOffset);
        yOffset += lineHeight;
        doc.text(`條碼編號: ${item.barcode || '-'}`, margin, yOffset);
        yOffset += lineHeight + 5;

        // 取得 SVG 元素
        const svgId = 'barcodeSvgAll-' + item.item_id;
        const svgElement = document.getElementById(svgId);
        if (svgElement) {
          try {
            // 將 SVG 轉成 XML 字串
            const svgData = new XMLSerializer().serializeToString(svgElement);

            // 建立 Canvas
            const canvas = document.createElement('canvas');
            canvas.width = 320;
            canvas.height = 100;
            const ctx = canvas.getContext('2d');

            // 建立 Image 元素
            const img = new Image();

            // 將 SVG 轉為 Data URL
            const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
            const url = URL.createObjectURL(svgBlob);

            await new Promise((resolve, reject) => {
              img.onload = () => {
                // 清空 Canvas
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                // 繪製圖片到 Canvas
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                URL.revokeObjectURL(url);
                resolve();
              };
              img.onerror = (e) => {
                URL.revokeObjectURL(url);
                console.warn('SVG 轉圖片載入失敗', e);
                resolve(); // 失敗也繼續
              };
              img.src = url;
            });

            // 取得 Canvas Data URL
            const imgData = canvas.toDataURL('image/png');

            // 加入 PDF
            doc.addImage(imgData, 'PNG', (pageWidth - barcodeImgWidth) / 2, yOffset, barcodeImgWidth, barcodeImgHeight);
            yOffset += barcodeImgHeight + spacing;

          } catch (e) {
            console.warn(`匯出條碼圖片失敗: ${item.item_id}`, e);
            yOffset += barcodeImgHeight + spacing;
          }
        } else {
          yOffset += barcodeImgHeight + spacing;
        }
      }

      doc.save('barcodes_with_text.pdf');
    }
  }
}).mount('#app');